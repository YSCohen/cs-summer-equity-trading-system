import os

postgres_port_number = int(os.getenv("POSTGRES_PORT", "5432"))
postgres_docker_name = os.getenv("POSTGRES_HOST", "localhost")
postgres_user = os.getenv("POSTGRES_USER", "postgres")
postgres_password = os.getenv("POSTGRES_PASSWORD", "password")
postgres_db = os.getenv("POSTGRES_DB", "trading")

redis_port_number = int(os.getenv("REDIS_PORT", "6379"))
redis_host = os.getenv("REDIS_HOST", "localhost")

TRADE_STREAM = os.getenv("TRADE_STREAM")

DAY_IN_SEC = 24 * 60 * 60

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"
