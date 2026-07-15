Data layer: the Postgres schema and the Rust workers that keep it in sync with Redis.

- **`init.sql`** — bootstraps the `trading` database: `users`, `accounts`, `positions`, `trades` tables plus `*_sync_stage` unlogged staging tables used by the syncers for bulk upserts, and grants for the `trade_admin` app user.
- **`redis-postgres-syncers/`** — the Rust workers that move data between Redis (hot path, written by the API) and Postgres (persistence). See [`redis-postgres-syncers/README.md`](redis-postgres-syncers/README.md).
