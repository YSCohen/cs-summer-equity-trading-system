#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "msgpack>=1.2.1",
#     "redis>=8.0.0",
# ]
# ///

# for testing the trade writer. send A LOT of trades to redis

import asyncio
import random
import string
import time
import uuid
import msgpack
import redis.asyncio as aioredis

redis_client = aioredis.Redis(host="localhost", port=6379, db=0)


async def individual_account(trade: dict):
    pass


async def make_fake_accounts():
    pass

if __name__ == "__main__":
    asyncio.run(generate_fake_trades())
