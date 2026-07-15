FastAPI backend for booking and querying trades. Reads/writes Postgres for persistence and Redis for fast reads, and authenticates requests via a session cookie.

### Components (`app/`)
- `routers/` — `auth`, `accounts`, `positions`, `trades`, `health`: the API surface.
- `services/` — business logic behind each router (account/position/trade services, S&P ticker validation).
- `models/` — Pydantic request/response models.
- `core/` — Postgres pool, Redis client, config, security (cookie auth), logging.
- `middleware/` — request logging.

### Endpoints
- **Auth**: `POST /register`, `POST /login`, `POST /logout`
- **Accounts**: `POST /users/account`, `POST /users/add_account/{account_id}`, `PATCH /users/update_account_details/{account_id}`, `GET /users/allaccounts`
- **Positions**: `GET /positions`, `GET /positions/accounts/{account_id}`, `GET /positions/ticker/{ticker}`, `GET /positions/accounts/{account_id}/ticker/{ticker}`
- **Trades**: `GET /tickers`, `POST /trade` (single or batch), `GET /trades`, `GET /trade/{trade_id}`, `PATCH /edit_trade/{trade_id}`
- **Health**: `GET /probe`

All routes except auth verify the session cookie. Trades and positions are written to Postgres and mirrored into Redis for the `db-syncer`/`trade-writer` workers to pick up (see [`db/redis-postgres-syncers/README.md`](../db/redis-postgres-syncers/README.md)).

Requires Postgres, Redis, and the logging stack to be up before it will start.
