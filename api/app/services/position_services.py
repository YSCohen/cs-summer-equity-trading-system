from fastapi import HTTPException
import json
from app.core.redis import redis_client, redis_dictionaries
from app.core.logging import logger


async def get_all_users_positions(user_id: str):
    # Get User data to check their accounts
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    user_data = json.loads(raw_user)

    positions = {}

    # Grab all positions for checking
    raw_positions = await redis_client.hgetall(redis_dictionaries[2])

    for x in raw_positions.values():
        x_positions = json.loads(x)
        if (
            x_positions["account_id"] in user_data["accounts_associated"]
        ):  # This positions is your account
            raw_account = await redis_client.hget(
                redis_dictionaries[1], x_positions["account_id"]
            )
            real_account = json.loads(raw_account)
            if (
                x_positions["account_id"] not in positions
            ):  # First time adding a position for that account
                positions[x_positions["account_id"]] = [
                    {
                        "account_name": real_account["account_name"],
                        "symbol_ticker": x_positions["symbol_ticker"],
                        "quantity": x_positions["quantity"],
                        "created_at": x_positions["created_at"],
                        "updated_at": x_positions["updated_at"],
                    }
                ]
            else:  # This account already processed at least one position
                positions[x_positions["account_id"]].append(
                    {
                        "account_name": real_account["account_name"],
                        "symbol_ticker": x_positions["symbol_ticker"],
                        "quantity": x_positions["quantity"],
                        "created_at": x_positions["created_at"],
                        "updated_at": x_positions["updated_at"],
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

    positions = {}

    # Grab all positions for checking
    raw_positions = await redis_client.hgetall(redis_dictionaries[2])

    for x in raw_positions.values():
        x_positions = json.loads(x)
        if x_positions["account_id"] == account_id:  # If this position is your account
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

    positions = {}

    # Grab all positions for checking
    raw_positions = await redis_client.hgetall(redis_dictionaries[2])

    for x in raw_positions.values():
        x_positions = json.loads(x)
        if (
            x_positions["account_id"] in user_data["accounts_associated"]
            and x_positions["symbol_ticker"] == ticker
        ):  # You own this account and it's the right ticker
            raw_account = await redis_client.hget(
                redis_dictionaries[1], x_positions["account_id"]
            )
            real_account = json.loads(raw_account)
            positions[x_positions["account_id"]] = [
                {
                    "account_name": real_account["account_name"],
                    "symbol_ticker": x_positions["symbol_ticker"],
                    "quantity": x_positions["quantity"],
                    "created_at": x_positions["created_at"],
                    "updated_at": x_positions["updated_at"],
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

    positions = {}

    # Grab all positions for checking
    raw_positions = await redis_client.hgetall(redis_dictionaries[2])

    for x in raw_positions.values():
        x_positions = json.loads(x)
        if (
            x_positions["account_id"] == account_id
            and x_positions["symbol_ticker"] == ticker
        ):  # Correct account and ticker
            positions[x_positions["symbol_ticker"]] = x_positions["quantity"]
            break  # only one account and one ticker
    return positions
