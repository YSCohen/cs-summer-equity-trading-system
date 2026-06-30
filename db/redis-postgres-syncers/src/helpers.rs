//! common functions for these bins

use std::env;
use tracing::debug;
use tracing_loki::url::Url;
use tracing_subscriber::{filter::LevelFilter, layer::SubscriberExt, util::SubscriberInitExt};

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
