#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "redis>=8.0.0",
# ]
# ///

# for testing the trade writer. send A LOT of trades to redis

import asyncio
import json
import random
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

NAMES = [
    "AAA",
    "BBB",
    "CCC",
    "DDD",
    "EEE",
    "FFF",
    "GGG",
    "HHH",
    "III",
    "JJJ",
    "KKK",
    "LLL",
    "MMM",
    "NNN",
    "OOO",
    "PPP",
    "QQQ",
    "RRR",
    "SSS",
    "TTT",
    "UUU",
    "VVV",
    "WWW",
    "XXX",
    "YYY",
    "ZZZ",
]


redis_client = aioredis.Redis(host="localhost", port=6379, db=0)


async def individual_account(account_name: str):
    account_id = str(uuid.uuid4())
    positions = []
    now = datetime.now(timezone.utc).isoformat()
    account_data = {
        "account_name": account_name,
        "positions": positions,
        "can_short": bool(random.getrandbits(1)),
        "created_at": now,
        "updated_at": now,
    }

    await redis_client.hset("accounts", account_id, json.dumps(account_data))


async def make_fake_accounts():
    try:
        for name in NAMES:
            await individual_account(name)
    finally:
        # Gracefully close the Redis connection pool
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(make_fake_accounts())
