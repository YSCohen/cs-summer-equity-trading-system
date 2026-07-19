import os
import math

postgres_port_number = int(os.getenv("POSTGRES_PORT", "5432"))
postgres_docker_name = os.getenv("POSTGRES_HOST", "localhost")
postgres_user = os.getenv("POSTGRES_USER", "postgres")
postgres_password = os.getenv("POSTGRES_PASSWORD", "password")
postgres_db = os.getenv("POSTGRES_DB", "trading")

redis_port_number = int(os.getenv("REDIS_PORT", "6379"))
redis_host = os.getenv("REDIS_HOST", "localhost")
max_pods = int(os.getenv("REDIS_MAX_PODS", 20))
server_max_clients = int(os.getenv("REDIS_SERVER_MAX_CLIENTS", 10000))
surge_pct = int(os.getenv("ROLLOUT_SURGE_PCT", 25))


peak_pods_during_rollout = max_pods * (1 + (surge_pct / 100))

safe_target_connections = server_max_clients * 0.60

computed_max_connections = math.floor(
    safe_target_connections / peak_pods_during_rollout
)

TRADE_STREAM = os.getenv("TRADE_STREAM")

DAY_IN_SEC = 24 * 60 * 60

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mysecretkey")
ALGORITHM = "HS256"
