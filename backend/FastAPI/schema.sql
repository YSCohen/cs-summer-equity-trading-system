CREATE TABLE IF NOT EXISTS trades (
    trade_id UUID PRIMARY KEY,

    account_id UUID NOT NULL,
    user_id UUID NOT NULL,

    direction VARCHAR(4) NOT NULL
        CHECK (direction IN ('Buy', 'Sell')),

    symbol_ticker VARCHAR(10) NOT NULL,

    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,

    quantity INTEGER NOT NULL,

    price NUMERIC(18,8) NOT NULL,

    other_account UUID
);