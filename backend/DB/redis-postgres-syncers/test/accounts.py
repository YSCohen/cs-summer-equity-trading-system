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

ACCOUNT_NAMES = [
    "savings",
    "checking",
    "investing",
    "ira",
    "trust fund",
    "risky",
    "bonds",
    "pyramid scheme",
    "piggy bank",
    "under mattress",
    "long term",
    "dept. cloud credits",
    "students AI credits",
]


redis_client = aioredis.Redis(host=os.getenv("REDIS_HOST", "localhost"))


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
    print(f"[NEW ACCOUNT] {account_name} - {account_id}")


async def make_fake_accounts():
    try:
        for name in ACCOUNT_NAMES:
            await individual_account(name)
    finally:
        # Gracefully close the Redis connection pool
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(make_fake_accounts())
