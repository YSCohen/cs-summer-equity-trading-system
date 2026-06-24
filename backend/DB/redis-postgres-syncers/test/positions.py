#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "redis>=8.0.0",
# ]
# ///

import asyncio
import json
import os
import random
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

TICKERS = [
    "AAPL",
    "MSFT",
    "AMZN",
    "NVDA",
    "META",
    "GOOGL",
    "GOOG",
    "LLY",
    "AVGO",
    "TSLA",
    "JPM",
    "CMCSA",
    "NKE",
    "DHR",
    "TXN",
]


redis_client = aioredis.Redis(host=os.getenv("REDIS_HOST", "localhost"))


async def individual_account(symbol: str):
    account_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    account_data = {
        "account_id": account_id,
        "symbol_ticker": symbol,
        "quantity": random.randint(1, 100),
        "created_at": now,
        "updated_at": now,
    }

    await redis_client.hset("positions", account_id, json.dumps(account_data))
    print(f"[NEW POSITION] {symbol} - {account_id}")


async def make_fake_positions():
    try:
        for symbol in TICKERS:
            await individual_account(symbol)
    finally:
        # Gracefully close the Redis connection pool
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(make_fake_positions())
