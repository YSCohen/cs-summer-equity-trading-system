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
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

USERNAMES = [
    "Alice",
    "Bob",
    "Carol",
    "David",
    "Eve",
    "Frank",
    "Grace",
    "Ivan",
    "Judy",
    "Mallory",
    "Oscar",
    "Peggy",
    "Rupert",
]


redis_client = aioredis.Redis(host=os.getenv("REDIS_HOST", "localhost"))


async def individual_user(username: str):
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    account_data = {
        "username": username,
        "oauth_key": "sandwich",
        "accounts_associated": [],
        "created_at": now,
        "updated_at": now,
    }

    await redis_client.hset("users", user_id, json.dumps(account_data))
    print(f"[NEW USER] {username} - {user_id}")


async def make_fake_users():
    try:
        for name in USERNAMES:
            await individual_user(name)
    finally:
        # Gracefully close the Redis connection pool
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(make_fake_users())
