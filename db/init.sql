CREATE TYPE trade_direction AS ENUM ('Buy', 'Sell');

CREATE TABLE trades (
    trade_id UUID PRIMARY KEY,
    account_id UUID, -- accounts
    user_id UUID, -- users
    direction trade_direction,
    symbol_ticker TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    quantity INT,
    price NUMERIC,
    other_account UUID -- accounts
);

CREATE TABLE positions (
    position_id UUID PRIMARY KEY,
    account_id UUID, -- accounts
    symbol_ticker TEXT,
    quantity INT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE accounts (
    account_id UUID PRIMARY KEY,
    account_name TEXT,
    positions UUID[], -- positions
    can_short BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    username TEXT,
    oauth_key TEXT,
    accounts_associated UUID[], -- accounts
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- STAGING TABLES (ignore)

CREATE UNLOGGED TABLE positions_sync_stage (
    position_id UUID PRIMARY KEY,
    account_id UUID, -- accounts
    symbol_ticker TEXT,
    quantity INT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE UNLOGGED TABLE accounts_sync_stage (
    account_id UUID PRIMARY KEY,
    account_name TEXT,
    positions UUID[], -- positions
    can_short BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE UNLOGGED TABLE users_sync_stage (
    user_id UUID PRIMARY KEY,
    username TEXT,
    oauth_key TEXT,
    accounts_associated UUID[], -- accounts
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
