//! copy positions, accounts, users from redis to postgres

use dotenvy::dotenv;
use futures_util::SinkExt;
use redis::AsyncCommands;
use redis::streams::{StreamReadOptions, StreamReadReply};
use serde::Deserialize;
use std::env;
use std::fmt::Write;
use tokio_postgres::NoTls;
use tracing::{error, info, warn};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    // Run the main pipeline and catch any fatal initialization errors
    if let Err(err) = run().await {
        error!(%err, "Fatal application initialization error");
        std::process::exit(1);
    }
}

async fn run() -> Result<(), Box<dyn std::error::Error>> {
    let _ = dotenv();

    let pg_config = env::var("POSTGRES_CONFIG").map_err(|_| "POSTGRES_CONFIG must be set")?;
    let redis_url = env::var("REDIS_URL").map_err(|_| "REDIS_URL must be set")?;
    let stream_name = env::var("REDIS_STREAM_NAME").map_err(|_| "REDIS_STREAM_NAME must be set")?;
    let consumer_group =
        env::var("REDIS_CONSUMER_GROUP").map_err(|_| "REDIS_CONSUMER_GROUP must be set")?;
    let worker_name = env::var("WORKER_NAME").map_err(|_| "WORKER_NAME must be set")?;

    info!("read env vars");

    // Connect to postgres
    let (pg_client, connection) = tokio_postgres::connect(&pg_config, NoTls).await?;
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            error!("PostgreSQL connection driver error: {}", e);
        }
    });
    info!("connected to postgres");

    // Connect to redis
    let redis_client = redis::Client::open(redis_url)?;
    let mut redis_conn = redis_client.get_multiplexed_async_connection().await?;
    info!("connected to redis");

    // TODO: copy redis to postgres

    Ok(())
}
