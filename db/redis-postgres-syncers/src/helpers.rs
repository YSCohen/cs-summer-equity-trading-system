//! common functions for these bins

use bytes::Bytes;
use futures_util::SinkExt;
use std::env;
use std::error::Error;
use tokio_postgres::{Client, CopyInSink, NoTls};
use tracing::{debug, error};
use tracing_loki::url::Url;
use tracing_subscriber::{filter::LevelFilter, layer::SubscriberExt, util::SubscriberInitExt};

/// Read a required environment variable, or return a descriptive error.
pub fn require_env(name: &str) -> Result<String, Box<dyn Error>> {
    env::var(name).map_err(|_| format!("{name} must be set").into())
}

/// Open a multiplexed async redis connection.
pub async fn connect_redis(
    url: String,
) -> Result<redis::aio::MultiplexedConnection, Box<dyn Error>> {
    let client = redis::Client::open(url)?;
    let conn = client.get_multiplexed_async_connection().await?;
    debug!("connected to redis");
    Ok(conn)
}

/// Connect to postgres and spawn the connection driver in the background.
pub async fn connect_postgres(config: &str) -> Result<Client, Box<dyn Error>> {
    let (client, connection) = tokio_postgres::connect(config, NoTls).await?;
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            error!(?e, "postgres connection driver error");
        }
    });
    debug!("connected to postgres");
    Ok(client)
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

    debug!("connected to loki");

    Ok(())
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
