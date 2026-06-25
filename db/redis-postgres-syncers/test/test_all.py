#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "msgpack>=1.2.1",
#     "redis>=8.0.0",
# ]
# ///

import asyncio
from datetime import datetime

import accounts
import positions
import trades
import users

if __name__ == "__main__":
    asyncio.run(trades.generate_fake_trades())
    asyncio.run(users.make_fake_users())
    asyncio.run(accounts.make_fake_accounts())
    asyncio.run(positions.make_fake_positions())
    
    # Record completion time
    print(f"🏁 Test suite finished at: {datetime.now().isoformat()}")
