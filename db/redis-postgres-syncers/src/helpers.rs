//! common functions for these bins

use bytes::Bytes;
use futures_util::SinkExt;
use serde::Deserialize;
use std::env;
use std::error::Error;
use tokio_postgres::{Client, CopyInSink, NoTls};
use tracing::{debug, error, info, trace};
use tracing_loki::url::Url;
use tracing_subscriber::{filter::LevelFilter, layer::SubscriberExt, util::SubscriberInitExt};

/// Read a required environment variable, or return a descriptive error.
pub fn require_env(name: &str) -> Result<String, Box<dyn Error>> {
    env::var(name).map_err(|_| format!("{name} must be set").into())
}

/// Log a specific fatal error, wait 1/2 sec, then exit
///
/// Returns `!` so it can be used directly in a `match` arm
pub async fn fatal(message: &str, err: impl std::fmt::Debug) -> ! {
    error!(?err, message);
    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
    std::process::exit(1);
}

/// Open a multiplexed async redis connection, or log the error and exit.
pub async fn connect_redis(url: String) -> redis::aio::MultiplexedConnection {
    let client = match redis::Client::open(url) {
        Ok(client) => client,
        Err(e) => fatal("failed to open redis client", e).await,
    };
    match client.get_multiplexed_async_connection().await {
        Ok(conn) => {
            debug!("connected to redis");
            conn
        }
        Err(e) => fatal("failed to connect to redis", e).await,
    }
}

/// Connect to postgres and spawn the connection driver, or log the error and exit.
pub async fn connect_postgres(config: &str) -> Client {
    let (client, connection) = match tokio_postgres::connect(config, NoTls).await {
        Ok(pair) => pair,
        Err(e) => fatal("failed to connect to postgres", e).await,
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

#[derive(Debug, Deserialize)]
struct Record {
    #[serde(rename = "Symbol")]
    symbol: String,
}

pub async fn fetch_sp500_symbols() -> Result<Vec<String>, Box<dyn Error>> {
    const URL: &str = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv";
    let response = reqwest::get(URL)
        .await
        .map_err(|e| format!("request for S&P 500 csv failed: {e:?}"))?
        .text()
        .await
        .map_err(|e| format!("reading S&P 500 csv body failed: {e:?}"))?;
    debug!("fetched S&P 500 csv ({} bytes)", response.len());

    let mut rdr = csv::Reader::from_reader(response.as_bytes());
    let mut symbols = Vec::new();

    for result in rdr.deserialize() {
        let record: Record = result.map_err(|e| format!("malformed row in S&P 500 csv: {e:?}"))?;
        // Fix for symbols that Yahoo represents differently (e.g., BRK.B instead of BRK-B)
        let formatted_symbol = record.symbol.replace('.', "-");
        trace!(symbol = %formatted_symbol, "parsed symbol");
        symbols.push(formatted_symbol);
    }
    debug!("parsed {} symbols from S&P 500 csv", symbols.len());

    Ok(symbols)
}
