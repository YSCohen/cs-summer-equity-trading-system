from fastapi import FastAPI
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from app.core.database import create_pool
from app.core.redis import redis_client
from app.core.logging import logger
from app.services import ticker_service
from app.middleware.logging_middleware import logging_middleware

from app.routers import (
    auth,
    accounts,
    positions,
    trades,
    health,
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting up API")

    try:
        app.state.pg_pool = await create_pool()

        logger.info("Synced with postgres")

    except Exception as e:
        logger.error(f"PostgreSQL startup failure: {e}")
        raise

    try:
        await redis_client.ping()

        logger.info("Redis connected")

    except Exception as e:
        logger.error(f"Redis startup failure: {e}")
        raise

    try:
        ticker_service.valid_tickers = ticker_service.load_sp500()

        logger.info("Loaded S&P Tickers")

    except Exception as e:
        logger.error(f"Ticker load failure: {e}")
        raise

    yield

    await app.state.pg_pool.close()
    await redis_client.aclose()

    logger.info("Closed connection to Postgres")
    logger.info("Closing down API")


app = FastAPI(lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(positions.router)
app.include_router(trades.router)
app.include_router(health.router)

app.middleware("http")(logging_middleware)
