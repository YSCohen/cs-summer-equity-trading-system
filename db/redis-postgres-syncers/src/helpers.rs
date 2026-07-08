//! common functions for these bins

use bytes::Bytes;
use futures_util::SinkExt;
use std::env;
use std::error::Error;
use tokio_postgres::{Client, CopyInSink, NoTls};
use tracing::{debug, error, info};
use tracing_loki::url::Url;
use tracing_subscriber::{filter::LevelFilter, layer::SubscriberExt, util::SubscriberInitExt};

/// Read a required environment variable, or return a descriptive error.
pub fn require_env(name: &str) -> Result<String, Box<dyn Error>> {
    env::var(name).map_err(|_| format!("{name} must be set").into())
}

/// Open a multiplexed async redis connection, or log the error and exit.
pub async fn connect_redis(url: String) -> redis::aio::MultiplexedConnection {
    let client = match redis::Client::open(url) {
        Ok(client) => client,
        Err(e) => {
            error!(?e, "failed to open redis client");
            std::process::exit(1);
        }
    };
    match client.get_multiplexed_async_connection().await {
        Ok(conn) => {
            debug!("connected to redis");
            conn
        }
        Err(e) => {
            error!(?e, "failed to connect to redis");
            std::process::exit(1);
        }
    }
}

/// Connect to postgres and spawn the connection driver, or log the error and exit.
pub async fn connect_postgres(config: &str) -> Client {
    let (client, connection) = match tokio_postgres::connect(config, NoTls).await {
        Ok(pair) => pair,
        Err(e) => {
            error!(?e, "failed to connect to postgres");
            std::process::exit(1);
        }
    };
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            error!(?e, "postgres connection driver error");
        }
    });
    debug!("connected to postgres");
    client
}

/// Map a postgres error to the most informative value to log.
///
/// A `DbError` carries the server-side detail (code, message, hint), so prefer
/// it when present and fall back to the raw error otherwise.
pub fn map_postgres_error(err: &tokio_postgres::Error) -> &dyn std::fmt::Debug {
    match err.as_db_error() {
        Some(db_error) => db_error,
        None => err,
    }
}

/// Send an entire COPY payload over a sink in one chunk and close it.
pub async fn send_copy_payload(
    sink: CopyInSink<Bytes>,
    payload: &str,
) -> Result<(), tokio_postgres::Error> {
    tokio::pin!(sink);
    sink.send(Bytes::from(payload.to_owned())).await?;
    sink.close().await?;
    Ok(())
}

pub fn init_tracing(app_name: &str) -> Result<(), Box<dyn std::error::Error>> {
    let loki_url = env::var("LOKI_URL").map_err(|_| "LOKI_URL must be set")?;
    let worker_name = env::var("WORKER_NAME").map_err(|_| "WORKER_NAME must be set")?;

    let loki_url = Url::parse(&loki_url)?;
    let (loki_layer, loki_task) = tracing_loki::builder()
        .label("app", app_name)?
        .label("pod", worker_name)?
        .build_url(loki_url)?;

    tracing_subscriber::registry()
        .with(LevelFilter::DEBUG)
        .with(loki_layer)
        // .with(tracing_subscriber::fmt::layer().with_writer(std::io::stdout))
        .init();

    tokio::spawn(loki_task);

    info!(build = %build_info(), "=== STARTING {app_name} ===");

    Ok(())
}

/// build metadata captured at compile time by `build.rs`
pub fn build_info() -> String {
    // env!() "Inspects an environment variable at compile time"
    let source = env!("BUILD_SOURCE");
    let hash = env!("BUILD_GIT_HASH");
    let built = env!("BUILD_UNIX_SECS")
        .parse::<i64>()
        .ok()
        .and_then(|secs| jiff::Timestamp::from_second(secs).ok())
        .map(|ts| ts.strftime("%Y-%m-%d %H:%M:%S UTC").to_string())
        .unwrap_or_else(|| "unknown".to_string());
    format!("built by {source}, from commit {hash}, on {built}")
}

pub async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install SIGTERM handler");
    };

    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    tokio::select! {
        () = ctrl_c => {},
        () = terminate => {},
    }
}
