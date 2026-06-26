from redis.asyncio import Redis
from app.core.config import redis_host, redis_port_number

redis_client = Redis(
    host=redis_host,
    port=redis_port_number,
    db=0,
)

redis_dictionaries = [
    "users",
    "accounts",
    "positions",
    "username"
]  # redis dicts TODO update these tables once agrred upon naming convention
