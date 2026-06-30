from app.core.redis import redis_client, redis_dictionaries

valid_tickers = set()


async def load_sp500():
    ticker_keys = await redis_client.hkeys(redis_dictionaries[4])
    return {
        ticker.decode() if isinstance(ticker, bytes) else ticker
        for ticker in ticker_keys
    }
