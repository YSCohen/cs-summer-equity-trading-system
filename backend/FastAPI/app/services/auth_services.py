from fastapi import HTTPException
from datetime import datetime, timezone
import json
import uuid
from app.core.redis import redis_client, redis_dictionaries
from app.core.security import pwd_context
from app.core.logging import logger


async def register_valid_user(username: str, password: str):
    # Check if the username already exists in Redis
    all_user_ids = await redis_client.hgetall(redis_dictionaries[0])

    positions = {
        key.decode() if isinstance(key, bytes) else key: json.loads(value)
        for key, value in all_user_ids.items()
    }  # Turn all positions into valid dictionaries and not bytes

    for user in positions.values():
        if username == user["username"]:
            logger.warning("Pre-existing username was used")
            raise HTTPException(status_code=409, detail="Username already exists")

    # Create new User data
    user_id = str(uuid.uuid4())
    account_ids = []
    now = datetime.now(timezone.utc).isoformat()
    user_data = {
        "username": username,
        "oauth_key": pwd_context.hash(password),
        "accounts_associated": account_ids,
        "created_at": now,
        "updated_at": now,
    }
    # send new User to redis
    await redis_client.hset(redis_dictionaries[0], user_id, json.dumps(user_data))

    return user_id


async def login_valid_user(username: str, password: str):
    # Get the User data from redis
    all_user_ids = await redis_client.hgetall(redis_dictionaries[0])

    positions = {
        key.decode() if isinstance(key, bytes) else key: json.loads(value)
        for key, value in all_user_ids.items()
    }  # Turn all positions into valid dictionaries and not bytes

    valid = False
    id = None

    for user_id, user in positions.items():
        if username == user["username"] and pwd_context.verify(
            password, user["oauth_key"]
        ):
            valid = True
            id = user_id

    if not valid:  # No such user exists or wrong password
        logger.warning("Invalid login attempt")
        raise HTTPException(status_code=401, detail="Wrong Username or Password")

    return id
