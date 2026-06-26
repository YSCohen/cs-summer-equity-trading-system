from fastapi import HTTPException
import json
from app.core.redis import redis_client, redis_dictionaries
from app.core.logging import logger


async def get_all_users_positions(user_id: str):
    # Get User data to check their accounts
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    user_data = json.loads(raw_user)

    pipe = redis_client.pipeline()

    users_accounts = set(user_data["accounts_associated"])

    for account in users_accounts:
        pipe.hget(redis_dictionaries[1], account)

    accounts = await pipe.execute()
    pipe = redis_client.pipeline()

    position_uuid_set = {}
    position_uuid_keys = []

    for raw_account_data in accounts:
        account_data = json.loads(raw_account_data)
        for position_uuid in account_data["positions"]:
            position_uuid_set[position_uuid] = account_data["account_name"]
            position_uuid_keys.append(position_uuid)
            pipe.hget(redis_dictionaries[2], position_uuid)

    results = await pipe.execute()

    positions = {}

    for position_uuid, raw_position in zip(position_uuid_keys, results):
        if raw_position is None:
            continue
        real_position_data = json.loads(raw_position)
        if (
            real_position_data["account_id"] not in positions
        ):  # First time adding a position for that account
            positions[real_position_data["account_id"]] = [
                {
                    "account_name": position_uuid_set[position_uuid],
                    "symbol_ticker": real_position_data["symbol_ticker"],
                    "quantity": real_position_data["quantity"],
                    "created_at": real_position_data["created_at"],
                    "updated_at": real_position_data["updated_at"],
                }
            ]
        else:  # This account already processed at least one position
            positions[real_position_data["account_id"]].append(
                {
                    "account_name": position_uuid_set[position_uuid],
                    "symbol_ticker": real_position_data["symbol_ticker"],
                    "quantity": real_position_data["quantity"],
                    "created_at": real_position_data["created_at"],
                    "updated_at": real_position_data["updated_at"],
                }
            )

    return positions


async def get_all_accounts_positions(account_id: str, user_id: str):
    # Get User data
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    user_data = json.loads(raw_user)

    # Confirm it's your account
    if account_id not in user_data["accounts_associated"]:
        logger.warning("Attempt to access account that the user does now own")
        raise HTTPException(
            status_code=401, detail="You do not have access to this account"
        )

    raw_account = await redis_client.hget(redis_dictionaries[1], account_id)
    account_data = json.loads(raw_account)

    positions = {}

    pipe = redis_client.pipeline()

    for position_uuid in account_data["positions"]:
        pipe.hget(redis_dictionaries[2], position_uuid)

    results = await pipe.execute()

    for x in results:
        x_positions = json.loads(x)
        positions[x_positions["symbol_ticker"]] = {
            "quantity": x_positions["quantity"],
            "created_at": x_positions["created_at"],
            "updated_at": x_positions["updated_at"],
        }
    return positions


async def get_all_users_ticker_positions(ticker: str, user_id: str):
    # Get User data
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    user_data = json.loads(raw_user)

    pipe = redis_client.pipeline()

    users_accounts = set(user_data["accounts_associated"])

    for account in users_accounts:
        pipe.hget(redis_dictionaries[1], account)

    accounts = await pipe.execute()
    pipe = redis_client.pipeline()

    position_uuid_set = {}
    position_uuid_keys = []

    for raw_account_data in accounts:
        account_data = json.loads(raw_account_data)
        for position_uuid in account_data["positions"]:
            position_uuid_set[position_uuid] = account_data["account_name"]
            position_uuid_keys.append(position_uuid)
            pipe.hget(redis_dictionaries[2], position_uuid)

    results = await pipe.execute()

    positions = {}

    for position_uuid, raw_position in zip(position_uuid_keys, results):
        if raw_position is None:
            continue
        real_position_data = json.loads(raw_position)
        if (
            real_position_data["symbol_ticker"] == ticker
        ):  # You own this account and it's the right ticker
            positions[real_position_data["account_id"]] = [
                {
                    "account_name": position_uuid_set[position_uuid],
                    "symbol_ticker": real_position_data["symbol_ticker"],
                    "quantity": real_position_data["quantity"],
                    "created_at": real_position_data["created_at"],
                    "updated_at": real_position_data["updated_at"],
                }
            ]
    return positions


async def get_account_ticker_position(ticker: str, account_id: str, user_id: str):
    # Grab User data
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    user_data = json.loads(raw_user)

    # Confirm you have access to this account
    if account_id not in user_data["accounts_associated"]:
        raise HTTPException(
            status_code=401, detail="You do not have access to this account"
        )

    raw_account = await redis_client.hget(redis_dictionaries[1], account_id)
    account_data = json.loads(raw_account)

    positions = {}

    pipe = redis_client.pipeline()

    for position_uuid in account_data["positions"]:
        pipe.hget(redis_dictionaries[2], position_uuid)

    results = await pipe.execute()

    for x in results:
        x_positions = json.loads(x)
        if x_positions["symbol_ticker"] == ticker:  # Correct account and ticker
            positions[x_positions["symbol_ticker"]] = x_positions["quantity"]
            break  # only one account and one ticker
    return positions
