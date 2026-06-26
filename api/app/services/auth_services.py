from fastapi import HTTPException
from datetime import datetime, timezone
import json
import uuid
from app.core.redis import redis_client, redis_dictionaries
from app.core.security import pwd_context
from app.core.logging import logger


async def register_valid_user(username: str, password: str):
    # Check if the username already exists in Redis
    old_uuid = await redis_client.hget(redis_dictionaries[3], username)

    if old_uuid:
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
    await redis_client.hset(redis_dictionaries[3], username, user_id)

    return user_id


async def login_valid_user(username: str, password: str):
    # Get the User data from redis
    old_uuid = await redis_client.hget(redis_dictionaries[3], username)

    if not old_uuid:
        logger.warning("Invalid login attempt")
        raise HTTPException(status_code=401, detail="Wrong Username or Password")

    old_uuid = old_uuid.decode() if isinstance(old_uuid, bytes) else old_uuid
    
    raw_user_data = await redis_client.hget(redis_dictionaries[0], old_uuid)
    real_user_data = json.loads(raw_user_data)
    if not pwd_context.verify(password, real_user_data["oauth_key"]):
        logger.warning("Invalid login attempt")
        raise HTTPException(status_code=401, detail="Wrong Username or Password")

    return old_uuid
