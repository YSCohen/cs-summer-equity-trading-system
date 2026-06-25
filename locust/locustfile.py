from locust import HttpUser, task, between
import uuid
import random


class EquityTradingUser(HttpUser):
    # Simulates a user waiting 1 to 3 seconds between actions

    wait_time = between(1, 3)

    def on_start(self):
        # create unique user
        username = f"user_{uuid.uuid4().hex[:8]}"

        self.client.post(
            "/register", json={"username": username, "password": "password123"}
        )

        response = self.client.post(
            "/users/account", params={"account_name": "Trading", "can_short": True}
        )

        self.account_id = response.json()["account_id"]

    @task(25)
    def create_trade(self):
        ticker = random.choice([
            "AAPL",
            "MSFT",
            "GOOG",
            "NVDA",
            "AMZN"
        ])

        self.client.post(
            "/trade",
            json=[
                {
                    "account_id": self.account_id,
                    "direction": "Buy",
                    "ticker": ticker,
                    "quantity": 100,
                    "price": "200.50",
                }
            ],
        )

    @task(5)
    def get_positions(self):
        self.client.get("/positions")

    @task(2)
    def get_trades(self):
        self.client.get("/trades")

    @task(1)
    def check_health(self):
        self.client.get("/probe")
