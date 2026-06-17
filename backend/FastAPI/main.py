from fastapi import FastAPI, Response, HTTPException
from redis import Redis
import jwt
import uuid
import json
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone

app = FastAPI()

redis_port_number = (
    6379  # Default Redis port TODO update this port once agreed upon port
)
redis_host = "localhost"  # Redis host address TODO update this address once agreed upon
redis_dictionaries = [
    "Users",
    "Accounts",
    "Tickers",
    "Positions",
]  # redis dicts TODO update these tables once agrred upon naming convention

day_in_sec = 24 * 60 * 60  # Number of seconds in a day

secret_key = (
    "mysecretkey"  # Encryption Key for passwords TODO come up with something better
)
algorithm = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_cookie(user_id: uuid):

    payload = {
        "name": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=day_in_sec),
    }
    authentication_cookie = jwt.encode(payload, secret_key, algorithm=algorithm)
    return authentication_cookie


# Initialize Redis client
redis_client = Redis(host=redis_host, port=redis_port_number, db=0)


@app.post("/registerUser")
def register_user(username: str, password: str, response: Response):

    # Check if the username already exists in Redis
    if redis_client.hexists(redis_dictionaries[0], username):
        raise HTTPException(status_code=409, detail="Usernam already exists")

    # Create new User data
    user_id = str(uuid.uuid4())
    uuid_account_array = []
    now = datetime.now(timezone.utc).isoformat()
    user_data = {
        "user_id": user_id,
        "password_hash": pwd_context.hash(password),
        "accounts": uuid_account_array,
        "created_at": now,
        "updated_at": now,
    }

    # send new User to redis
    redis_client.hset(redis_dictionaries[0], username, json.dumps(user_data))

    # Create token for authentication
    authentication_cookie = create_cookie(user_id)
    response.set_cookie(
        key="session",
        value=authentication_cookie,
        httponly=True,
        samesite="lax",
        max_age=day_in_sec,
    )

    return {"message": "User registered successfully."}


@app.get("/login")
def login_user(username: str, password: str, response: Response):

    # Get the User data from redis
    raw_user = redis_client.hget(redis_dictionaries[0], username)
    if not raw_user:  # No such user exists
        raise HTTPException(status_code=401, detail="Wrong Username or Password")

    user_data = json.loads(raw_user)
    if not pwd_context.verify(password, user_data["password_hash"]):  # Wrong password
        raise HTTPException(status_code=401, detail="Wrong Username or Password")

    # Create token for authentication
    authentication_cookie = create_cookie(user_data["user_id"])
    response.set_cookie(
        key="session",
        value=authentication_cookie,
        httponly=True,
        samesite="lax",
        max_age=day_in_sec,
    )

    return {"message": "login succesful."}


@app.post("/logout")
def logout(response: Response):

    response.delete_cookie(key="session", httponly=True, samesite="lax")

    return {"message": "logged out"}
