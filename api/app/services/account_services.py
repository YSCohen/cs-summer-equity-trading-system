from fastapi import HTTPException
from datetime import datetime, timezone
import uuid
import json
from app.core.redis import redis_client, redis_dictionaries
from app.core.logging import logger


async def create_new_account(account_name: str, can_short: bool, user_id: str):
    # Create account
    account_id = str(uuid.uuid4())
    positions = []
    now = datetime.now(timezone.utc).isoformat()
    account_data = {
        "account_name": account_name,
        "positions": positions,
        "can_short": can_short,
        "created_at": now,
        "updated_at": now,
    }

    await redis_client.hset(redis_dictionaries[1], account_id, json.dumps(account_data))

    # Grab User to add Account to them
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    user_data = json.loads(raw_user)

    user_data["accounts_associated"].append(account_id)
    user_data["updated_at"] = now

    await redis_client.hset(redis_dictionaries[0], user_id, json.dumps(user_data))

    return account_id


async def add_account_to_user(account_id: str, user_id: str):
    # Get account to ensure it exists
    raw_account = await redis_client.hget(redis_dictionaries[1], account_id)
    if not raw_account:
        logger.warning("Invalid account given")
        raise HTTPException(status_code=404, detail="This account does not exist")

    # Grab User to add account to them
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    user_data = json.loads(raw_user)

    user_data["accounts_associated"].append(account_id)
    user_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await redis_client.hset(redis_dictionaries[0], user_id, json.dumps(user_data))

    return user_data["username"]


async def get_all_users_accounts(user_id: str):

    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    user_data = json.loads(raw_user)

    account_name = []
    for account in user_data["accounts_associated"]:
        account_raw = await redis_client.hget(redis_dictionaries[1], account)
        accont_real = json.loads(account_raw)
        account_name.append(accont_real["account_name"])

    return dict(zip(account_name, user_data["accounts_associated"]))
