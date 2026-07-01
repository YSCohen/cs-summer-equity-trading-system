from fastapi import HTTPException
import json
from app.core.redis import redis_client, redis_dictionaries
from app.core.logging import logger


async def get_all_users_positions(user_id: str):
    # Get User data to check their accounts
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    if raw_user is None:
        raise HTTPException(
            status_code=503, detail="The database has crashed, try again later"
        )
    user_data = json.loads(raw_user)

    # Gather all of the user's accounts
    pipe = redis_client.pipeline()

    users_accounts = set(user_data["accounts_associated"])

    for account in users_accounts:
        pipe.hget(redis_dictionaries[1], account)

    accounts = await pipe.execute()

    # Gathering all positions for each account
    pipe = redis_client.pipeline()

    position_uuid_to_account_name = {}
    position_uuid_keys = []

    for raw_account_data in accounts:
        if raw_account_data is None:
            continue
        account_data = json.loads(raw_account_data)
        for position_uuid in account_data["positions"]:
            position_uuid_to_account_name[position_uuid] = account_data["account_name"]
            position_uuid_keys.append(position_uuid)
            pipe.hget(redis_dictionaries[2], position_uuid)

    results = await pipe.execute()

    pipe = redis_client.pipeline()

    position_uuid_to_position_data = {}
    all_symbols_for_positions = []
    seen_symbols = set()

    for position_uuid, raw_position_data in zip(position_uuid_keys, results):
        if raw_position_data is None:
            continue
        real_position_data = json.loads(raw_position_data)
        position_uuid_to_position_data[position_uuid] = real_position_data
        ticker = real_position_data["symbol_ticker"]

        if ticker not in seen_symbols:
            all_symbols_for_positions.append(ticker)
            seen_symbols.add(ticker)
            pipe.hget(redis_dictionaries[4], ticker)

    # Gathering market data for each ticker
    results = await pipe.execute()

    symbol_market_data = {}

    for ticker, value in zip(all_symbols_for_positions, results):
        if value is None:
            continue
        symbol_market_data[ticker] = json.loads(value)

    # Actually loading the position data
    positions = {}

    for position_uuid in position_uuid_keys:
        if position_uuid not in position_uuid_to_position_data:
            continue
        position = position_uuid_to_position_data[position_uuid]
        market = symbol_market_data.get(position["symbol_ticker"])
        if market is None:
            continue
        positions.setdefault(position["account_id"], []).append(
            {
                "account_name": position_uuid_to_account_name[position_uuid],
                "symbol_ticker": position["symbol_ticker"],
                "quantity": position["quantity"],
                "latest_price": market["latest_price"],
                "open_price": market["open_price"],
                "position_value": position["quantity"] * market["latest_price"],
                "created_at": position["created_at"],
                "updated_at": position["updated_at"],
            }
        )

    return positions


async def get_all_accounts_positions(account_id: str, user_id: str):
    # Get User data
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    if raw_user is None:
        raise HTTPException(
            status_code=503, detail="The database has crashed, try again later"
        )
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

    pipe = redis_client.pipeline()

    real_positions = []
    all_symbols_for_positions = []
    seen_symbols = set()

    for position in results:
        real_position = json.loads(position)
        real_positions.append(real_position)
        ticker = real_position["symbol_ticker"]

        if ticker not in seen_symbols:
            all_symbols_for_positions.append(ticker)
            seen_symbols.add(ticker)
            pipe.hget(redis_dictionaries[4], ticker)

    results = await pipe.execute()

    symbol_market_data = {}

    for ticker, value in zip(all_symbols_for_positions, results):
        if value is None:
            continue
        symbol_market_data[ticker] = json.loads(value)

    for x_positions in real_positions:
        market = symbol_market_data.get(x_positions["symbol_ticker"])
        if not market:
            continue
        positions[x_positions["symbol_ticker"]] = {
            "quantity": x_positions["quantity"],
            "latest_price": market["latest_price"],
            "open_price": market["open_price"],
            "position_value": x_positions["quantity"] * market["latest_price"],
            "created_at": x_positions["created_at"],
            "updated_at": x_positions["updated_at"],
        }
    return positions


async def get_all_users_ticker_positions(ticker: str, user_id: str):
    # Get User data
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    if raw_user is None:
        raise HTTPException(
            status_code=503, detail="The database has crashed, try again later"
        )
    user_data = json.loads(raw_user)

    raw_symbol_data = await redis_client.hget(redis_dictionaries[4], ticker)
    if raw_symbol_data is None:
        raise HTTPException(status_code=422, detail="Ticker does not exist")
    real_symbol_data = json.loads(raw_symbol_data)

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
                    "latest_price": real_symbol_data["latest_price"],
                    "open_price": real_symbol_data["open_price"],
                    "position_value": real_position_data["quantity"]
                    * real_symbol_data["latest_price"],
                    "created_at": real_position_data["created_at"],
                    "updated_at": real_position_data["updated_at"],
                }
            ]
    return positions


async def get_account_ticker_position(ticker: str, account_id: str, user_id: str):
    # Grab User data
    raw_user = await redis_client.hget(redis_dictionaries[0], user_id)
    if raw_user is None:
        raise HTTPException(
            status_code=503, detail="The database has crashed, try again later"
        )
    user_data = json.loads(raw_user)

    # Confirm you have access to this account
    if account_id not in user_data["accounts_associated"]:
        raise HTTPException(
            status_code=401, detail="You do not have access to this account"
        )

    raw_symbol_data = await redis_client.hget(redis_dictionaries[4], ticker)
    if raw_symbol_data is None:
        raise HTTPException(status_code=422, detail="Ticker does not exist")
    real_symbol_data = json.loads(raw_symbol_data)

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
            positions[x_positions["symbol_ticker"]] = {
                "quantity": x_positions["quantity"],
                "latest_price": real_symbol_data["latest_price"],
                "open_price": real_symbol_data["open_price"],
                "position_value": x_positions["quantity"]
                * real_symbol_data["latest_price"],
            }
            break  # only one account and one ticker
    return positions
