Rust workspace of five binaries that move data between Redis (hot path) and Postgres (persistence), plus market data ingestion. Each binary is a long-running worker deployed as its own Kubernetes deployment/job.

### Binaries (`src/`)
- **`db-syncer`** — copies users, accounts, and positions from Redis to Postgres.
- **`trade-writer`** — reads booked trades off a Redis stream (written by the API) and writes them to Postgres.
- **`redis-populator`** — the reverse of `db-syncer`: reads users/accounts/positions from Postgres and rebuilds the Redis hashes. Runs once and exits — used for cold-cache bootstrap or restore after `make db-restore`/`make db-clear`.
- **`price-cacher`** — pulls current S&P 500 prices from the Yahoo Finance API and caches them in Redis.
- **`price-timeseries-cacher`** — stores historical S&P 500 prices in Redis as time series (1m raw data compacting into hourly/daily tiers), queryable via `TS.RANGE`.
- **`helpers.rs`** — shared library code (env config, tracing/Loki setup, Postgres helpers) used by all binaries.

### Building
`build_dev_images.nu` builds and pushes dev-tagged multi-arch images (`ghcr.io/sm26-industrial-software-dev/<bin>:dev`) via `Containerfile`, tagged with the current git commit. Run with no args to build all binaries, or pass specific binary names.

### Testing
`test/` holds Python integration tests (`test_all.py` plus per-entity `users.py`/`accounts.py`/`positions.py`/`trades.py`) that exercise the syncers against a live Redis/Postgres pair.
