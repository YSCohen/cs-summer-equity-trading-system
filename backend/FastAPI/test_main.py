import json
import jwt
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from main import app, secret_key, algorithm, day_in_sec
from unittest.mock import patch


# Test suite for the FastAPI app in `main.py`.
# - Uses `FakeRedisClient` to stub Redis so tests run offline.
# - `client` fixture provides a `TestClient(app)` instance.
# - Helper functions and targeted tests cover auth, accounts, and positions.


class FakeRedisStore:
    def __init__(self):
        self._hashes = {}
        self._streams = {}

    def hexists(self, name, key):
        return key in self._hashes.get(name, {})

    def hset(self, name, key, value):
        self._hashes.setdefault(name, {})[key] = value
        return 1

    def hget(self, name, key):
        return self._hashes.get(name, {}).get(key)

    def hgetall(self, name):
        return self._hashes.get(name, {}).copy()

    def xadd(self, stream_name, fields):
        self._streams.setdefault(stream_name, []).append(fields)
        return len(self._streams[stream_name])


class FakeRedisClientAsync:
    def __init__(self, store):
        self._store = store

    async def hexists(self, name, key):
        return self._store.hexists(name, key)

    async def hset(self, name, key, value):
        return self._store.hset(name, key, value)

    async def hget(self, name, key):
        return self._store.hget(name, key)

    async def hgetall(self, name):
        return self._store.hgetall(name)

    async def xadd(self, stream_name, fields):
        return self._store.xadd(stream_name, fields)


# The `fake_redis` fixture monkeypatches `main.redis_client` so that all
# Redis operations in the app use this in-memory stub during tests.


@pytest.fixture
def fake_redis():
    store = FakeRedisStore()
    async_client = FakeRedisClientAsync(store)
    with patch("main.redis_client", async_client):
        yield store


@pytest.fixture
def client(fake_redis):
    return TestClient(app)


# `register_user` is a small helper to call the `/register` endpoint.
# Tests use it to create an authenticated session and seed user state.


def register_user(client, username="testuser", password="password123"):
    return client.post(
        "/register",
        json={"username": username, "password": password},
    )


def login_user(client, username="testuser", password="password123"):
    return client.post(
        "/login",
        json={"username": username, "password": password},
    )


def create_expired_session(username="testuser"):
    return jwt.encode(
        {
            "username": username,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        secret_key,
        algorithm=algorithm,
    )


# ----------------
# Test classes
# ----------------
# Each class groups related endpoint tests (registration, login, accounts, etc.)


class TestUserRegistration:
    # Tests for `/register` behavior
    def test_register_new_user(self, client, fake_redis):
        response = register_user(client)
        assert response.status_code == 200
        assert response.json() == {"message": "User registered successfully."}
        assert "set-cookie" in response.headers

    def test_register_duplicate_username(self, client, fake_redis):
        register_user(client)
        response = register_user(client)

        assert response.status_code == 409
        assert response.json() == {"detail": "Username already exists"}

    def test_registration_sets_cookie(self, client, fake_redis):
        response = register_user(client)
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert "session=" in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=lax" in cookie_header


class TestUserLogin:
    # Tests for `/login` behavior
    def test_login_valid_credentials(self, client, fake_redis):
        register_user(client)
        response = login_user(client, username="testuser", password="password123")

        assert response.status_code == 200
        assert response.json() == {"message": "login succesful."}
        assert "set-cookie" in response.headers

    def test_login_invalid_username(self, client, fake_redis):
        response = login_user(client, username="nonexistent", password="password123")

        assert response.status_code == 401
        assert response.json() == {"detail": "Wrong Username or Password"}

    def test_login_wrong_password(self, client, fake_redis):
        register_user(client)
        response = login_user(client, username="testuser", password="wrongpassword")

        assert response.status_code == 401
        assert response.json() == {"detail": "Wrong Username or Password"}


class TestUserLogout:
    # Tests for `/logout` behavior
    def test_logout_deletes_cookie(self, client, fake_redis):
        response = client.post("/logout")

        assert response.status_code == 200
        assert response.json() == {"message": "logged out"}
        assert "set-cookie" in response.headers


class TestAccountManagement:
    # Tests around account creation and linking accounts to users
    def test_create_account_adds_account_to_user(self, client, fake_redis):
        register_user(client)

        response = client.post("/users/account?can_short=true")
        assert response.status_code == 200
        assert response.json() == {"message": "Account created"}

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        assert len(user_data["accounts"]) == 1
        account_id = user_data["accounts"][0]

        raw_account = fake_redis.hget("Accounts", account_id)
        account_data = json.loads(raw_account)
        assert account_data["can_short"] is True
        assert account_data["positions"] == []

    def test_add_account_to_user(self, client, fake_redis):
        register_user(client)

        account_id = "account-123"
        # Seed the Accounts table so the endpoint validates successfully
        account_data = {
            "positions": [],
            "can_short": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        fake_redis.hset("Accounts", account_id, json.dumps(account_data))

        response = client.post(f"/users/accounts/{account_id}")

        assert response.status_code == 200
        assert response.json() == {"message": "Account added to user testuser"}

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        assert account_id in user_data["accounts"]

    def test_add_account_returns_404_when_account_missing(self, client, fake_redis):
        register_user(client)

        response = client.post("/users/accounts/nonexistent-account")

        assert response.status_code == 404
        assert response.json() == {"detail": "This account does not exist"}


class TestPositions:
    # Tests for positions-related endpoints. These seed `Positions` and
    # (where required) `Tickers` so the validation logic in `main.py`
    # succeeds during tests.

    def create_pos_pos2_in_redis(self, fake_redis, account_id):
        fake_redis.hset(
            "Positions",
            "pos2",
            json.dumps(
                {
                    "Account_id": account_id,
                    "Ticker": "MSFT",
                    "Quantity": 5,
                    "Created_at": "2026-06-17T17:10:00Z",
                    "Updated_at": "2026-06-17T17:10:00Z",
                }
            ),
        )

    def create_pos_pos1_in_redis(self, fake_redis, account_id):
        fake_redis.hset(
            "Positions",
            "pos1",
            json.dumps(
                {
                    "Account_id": account_id,
                    "Ticker": "AAPL",
                    "Quantity": 10,
                    "Created_at": "2026-06-17T17:00:00Z",
                    "Updated_at": "2026-06-17T17:00:00Z",
                }
            ),
        )

    def setup_user_with_account(self, client):
        register_user(client)
        response = client.post("/users/account?can_short=false")
        assert response.status_code == 200

    def test_get_users_positions(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        self.create_pos_pos1_in_redis(fake_redis, account_id)
        self.create_pos_pos2_in_redis(fake_redis, account_id)

        response = client.get("/positions")
        assert response.status_code == 200

        expected = {
            "message": {
                account_id: [
                    {
                        "Ticker": "AAPL",
                        "Quantity": 10,
                        "Created_at": "2026-06-17T17:00:00Z",
                        "Updated_at": "2026-06-17T17:00:00Z",
                    },
                    {
                        "Ticker": "MSFT",
                        "Quantity": 5,
                        "Created_at": "2026-06-17T17:10:00Z",
                        "Updated_at": "2026-06-17T17:10:00Z",
                    },
                ]
            }
        }
        assert response.json() == expected


    def test_get_accounts_positions(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        self.create_pos_pos1_in_redis(fake_redis, account_id)

        response = client.get(f"/positions/accounts/{account_id}")
        assert response.status_code == 200
        assert response.json() == {
            "message": {
                "AAPL": {
                    "Quantity": 10,
                    "Created_at": "2026-06-17T17:00:00Z",
                    "Updated_at": "2026-06-17T17:00:00Z",
                }
            }
        }

    def test_get_users_positions_for_ticker(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        # Ensure ticker exists in Tickers table
        fake_redis.hset("Tickers", "AAPL", "true")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        self.create_pos_pos1_in_redis(fake_redis, account_id)

        response = client.get("/positions/ticker/AAPL")
        assert response.status_code == 200
        assert response.json() == {
            "message": {
                account_id: [
                    {
                        "Ticker": "AAPL",
                        "Quantity": 10,
                        "Created_at": "2026-06-17T17:00:00Z",
                        "Updated_at": "2026-06-17T17:00:00Z",
                    }
                ]
            }
        }

    def test_get_ticker_position_returns_404_for_invalid_ticker(
        self, client, fake_redis
    ):
        register_user(client)
        client.post("/users/account?can_short=false")

        response = client.get("/positions/ticker/INVALID")
        assert response.status_code == 404
        assert response.json() == {"detail": "This ticker does not exist"}

    def test_get_account_ticker_position_returns_404_for_invalid_ticker(
        self, client, fake_redis
    ):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        response = client.get(f"/positions/accounts/{account_id}/ticker/INVALID")
        assert response.status_code == 404
        assert response.json() == {"detail": "This ticker does not exist"}

    def test_get_accounts_positions_for_ticker(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        self.create_pos_pos1_in_redis(fake_redis, account_id)

        # Ensure ticker is present
        fake_redis.hset("Tickers", "AAPL", "true")

        response = client.get(f"/positions/accounts/{account_id}/ticker/AAPL")
        assert response.status_code == 200
        assert response.json() == {"message": {"AAPL": 10}}


class TestTradeEndpoint:
    # Tests for `/trade` cover validation of list payload shape, account/ticker
    # existence, user authorization, direction validation, and quantity rules.
    def test_create_buy_trade_creates_position(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")
        fake_redis.hset(
            "Accounts",
            account_id,
            json.dumps(
                {
                    "positions": [],
                    "can_short": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Buy",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 200
        assert response.json() == {"status": "success"}

    def test_create_buy_trade_updates_existing_position(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")
        fake_redis.hset(
            "Accounts",
            account_id,
            json.dumps(
                {
                    "positions": [],
                    "can_short": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
        fake_redis.hset(
            "Positions",
            "pos1",
            json.dumps(
                {
                    "Account_id": account_id,
                    "Ticker": "AAPL",
                    "Quantity": 10,
                    "Created_at": datetime.now(timezone.utc).isoformat(),
                    "Updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Buy",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        updated_raw_position = fake_redis.hget("Positions", "pos1")
        updated_position = json.loads(updated_raw_position)
        assert updated_position["Quantity"] == 15

    def test_create_trade_invalid_trade_data_returns_422_when_empty_list(
        self, client, fake_redis
    ):
        register_user(client)
        client.post("/users/account?can_short=false")

        response = client.post("/trade", json=[])

        assert response.status_code == 422
        assert response.json() == {"detail": "Invalid Trade Data"}

    def test_create_trade_invalid_ticker_returns_404(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset(
            "Accounts",
            account_id,
            json.dumps(
                {
                    "positions": [],
                    "can_short": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Buy",
                "ticker": "INVALID",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 404
        assert response.json() == {"detail": "This ticker does not exist"}

    def test_create_trade_account_missing_returns_404(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")
        fake_redis.hset("Tickers", "AAPL", "true")

        trade = [
            {
                "account_id": "missing-account",
                "user_id": "testuser",
                "direction": "Buy",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 404
        assert response.json() == {"detail": "This account does not exist"}

    def test_create_trade_unauthorized_user_id_returns_401(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")

        trade = [
            {
                "account_id": account_id,
                "user_id": "otheruser",
                "direction": "Buy",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 401
        assert response.json() == {"detail": "This user_id does not match your user_id"}

    def test_create_trade_unauthorized_account_access_returns_401(
        self, client, fake_redis
    ):
        register_user(client, username="user1", password="password1")
        client.post("/users/account?can_short=false")
        raw_user1 = fake_redis.hget("Users", "user1")
        user1_data = json.loads(raw_user1)
        account_id = user1_data["accounts"][0]

        register_user(client, username="user2", password="password2")
        login_user(client, username="user2", password="password2")

        raw_user2 = fake_redis.hget("Users", "user2")
        user2_data = json.loads(raw_user2)

        fake_redis.hset("Tickers", "AAPL", "true")

        trade = [
            {
                "account_id": account_id,
                "user_id": user2_data["user_id"],
                "direction": "Buy",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 401
        assert response.json() == {"detail": "You do not have access to this account"}

    def test_create_trade_invalid_direction_returns_422(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Hold",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 422
        assert response.json() == {"detail": "Not a valid Direction"}

    def test_create_trade_invalid_quantity_returns_422_for_negative(
        self, client, fake_redis
    ):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Buy",
                "ticker": "AAPL",
                "quantity": -1,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 422
        assert response.json() == {"detail": "Not a valid quantity value"}

    def test_create_trade_short_not_allowed_returns_403(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=false")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Sell",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 403
        assert response.json() == {"detail": "You do not have permission to short"}

    def test_create_trade_sell_with_short_permission_updates_position(
        self, client, fake_redis
    ):
        register_user(client)
        client.post("/users/account?can_short=true")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")

        # Seed an existing long position so the sell trade reduces quantity.
        fake_redis.hset(
            "Positions",
            "pos1",
            json.dumps(
                {
                    "Account_id": account_id,
                    "Ticker": "AAPL",
                    "Quantity": 10,
                    "Created_at": datetime.now(timezone.utc).isoformat(),
                    "Updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Sell",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        updated_raw_position = fake_redis.hget("Positions", "pos1")
        updated_position = json.loads(updated_raw_position)
        assert updated_position["Quantity"] == 5

    def test_create_trade_sell_with_short_permission_creates_negative_position(
        self, client, fake_redis
    ):
        register_user(client)
        client.post("/users/account?can_short=true")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Sell",
                "ticker": "AAPL",
                "quantity": 5,
                "price": "150.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        created_positions = fake_redis.hgetall("Positions")
        assert len(created_positions) == 1
        created_position = json.loads(list(created_positions.values())[0])
        assert created_position["Quantity"] == -5

    def test_create_multiple_trades_in_one_request(self, client, fake_redis):
        register_user(client)
        client.post("/users/account?can_short=true")

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        fake_redis.hset("Tickers", "AAPL", "true")
        fake_redis.hset("Tickers", "MSFT", "true")

        trade = [
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Buy",
                "ticker": "AAPL",
                "quantity": 2,
                "price": "150.00",
            },
            {
                "account_id": account_id,
                "user_id": user_data["user_id"],
                "direction": "Buy",
                "ticker": "MSFT",
                "quantity": 3,
                "price": "250.00",
            },
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        created_positions = fake_redis.hgetall("Positions")
        assert len(created_positions) == 2
        quantities = [
            json.loads(value)["Quantity"] for value in created_positions.values()
        ]
        assert set(quantities) == {2, 3}

    def test_create_trade_with_unknown_user_returns_404(self, client, fake_redis):
        client.cookies.set(
            "session",
            jwt.encode(
                {
                    "username": "ghostuser",
                    "iat": datetime.now(timezone.utc),
                    "exp": datetime.now(timezone.utc) + timedelta(seconds=day_in_sec),
                },
                secret_key,
                algorithm=algorithm,
            ),
        )

        fake_redis.hset("Tickers", "AAPL", "true")
        fake_redis.hset(
            "Accounts",
            "account-unknown",
            json.dumps(
                {
                    "positions": [],
                    "can_short": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )

        trade = [
            {
                "account_id": "account-unknown",
                "user_id": "ghostuser",
                "direction": "Buy",
                "ticker": "AAPL",
                "quantity": 1,
                "price": "1.00",
            }
        ]

        response = client.post("/trade", json=trade)

        assert response.status_code == 404
        assert response.json() == {"detail": "This user does not exist"}


class TestSecurityAndWorkflow:
    # Security checks and an end-to-end workflow test
    def test_unauthorized_access_to_other_account(self, client, fake_redis):
        register_user(client, username="user1", password="password1")
        response = client.post("/users/account?can_short=false")
        assert response.status_code == 200

        raw_user1 = fake_redis.hget("Users", "user1")
        user1_data = json.loads(raw_user1)
        account_id = user1_data["accounts"][0]

        with TestClient(app) as client2:
            client2.cookies.set("session", "")
            client2.post(
                "/register",
                json={"username": "user2", "password": "password2"},
            )
            not_allowed = client2.get(f"/positions/accounts/{account_id}")

        assert not_allowed.status_code == 401
        assert not_allowed.json() == {
            "detail": "You do not have access to this account"
        }

    def test_invalid_cookie_returns_401(self, client, fake_redis):
        register_user(client)
        client.cookies.set("session", "invalid-token")

        response = client.get("/positions")
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid token"}

    def test_expired_cookie_returns_401(self, client, fake_redis):
        register_user(client)
        client.cookies.set("session", create_expired_session())

        response = client.get("/positions")
        assert response.status_code == 401
        assert response.json() == {"detail": "Token expired"}

    def test_full_registration_account_position_workflow(self, client, fake_redis):
        register_user(client)
        response = client.post("/users/account?can_short=false")
        assert response.status_code == 200

        raw_user = fake_redis.hget("Users", "testuser")
        user_data = json.loads(raw_user)
        account_id = user_data["accounts"][0]

        # Ensure tickers exist for the workflow
        fake_redis.hset("Tickers", "AAPL", "true")
        fake_redis.hset("Tickers", "GOOG", "true")

        fake_redis.hset(
            "Positions",
            "pos1",
            json.dumps(
                {
                    "Account_id": account_id,
                    "Ticker": "AAPL",
                    "Quantity": 10,
                    "Created_at": "2026-06-17T17:00:00Z",
                    "Updated_at": "2026-06-17T17:00:00Z",
                }
            ),
        )
        fake_redis.hset(
            "Positions",
            "pos2",
            json.dumps(
                {
                    "Account_id": account_id,
                    "Ticker": "GOOG",
                    "Quantity": 3,
                    "Created_at": "2026-06-17T17:05:00Z",
                    "Updated_at": "2026-06-17T17:05:00Z",
                }
            ),
        )

        positions_response = client.get("/positions")
        assert positions_response.status_code == 200
        assert account_id in positions_response.json()["message"]

        account_positions_response = client.get(f"/positions/accounts/{account_id}")
        assert account_positions_response.status_code == 200
        assert account_positions_response.json()["message"]["AAPL"]["Quantity"] == 10

        ticker_positions_response = client.get("/positions/ticker/AAPL")
        assert ticker_positions_response.status_code == 200
        assert account_id in ticker_positions_response.json()["message"]

        account_ticker_response = client.get(
            f"/positions/accounts/{account_id}/ticker/AAPL"
        )
        assert account_ticker_response.status_code == 200
        assert account_ticker_response.json() == {"message": {"AAPL": 10}}

        logout_response = client.post("/logout")
        assert logout_response.status_code == 200

        expired_access = client.get("/positions")
        assert expired_access.status_code == 401
        assert expired_access.json() == {"detail": "Not authenticated"}
