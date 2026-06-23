//! copy positions, accounts, users from redis to postgres

use bytes::Bytes;
use dotenvy::dotenv;
use futures_util::SinkExt;
use std::env;
use std::error::Error;
use std::fmt::Write;
use tokio_postgres::NoTls;
use tracing::{error, info, warn};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    info!("STARTING DB SYNCER");

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
    let redis_conn = redis_client.get_multiplexed_async_connection().await?;
    info!("connected to redis");

    sync_accounts(pg_client, redis_conn).await?;

    Ok(())
}

#[derive(serde::Deserialize)]
struct AccountData {
    account_name: String,
    positions: Vec<String>,
    can_short: bool,
    created_at: String,
    updated_at: String,
}

async fn sync_accounts(
    pg_client: tokio_postgres::Client,
    mut redis_conn: redis::aio::MultiplexedConnection,
) -> Result<(), Box<dyn Error + 'static>> {
    info!("Starting account sync...");

    let accounts: std::collections::HashMap<String, String> = redis::cmd("HGETALL")
        .arg("accounts")
        .query_async(&mut redis_conn)
        .await?;
    info!(
        "Found {} accounts in Redis. Starting migration...",
        accounts.len()
    );

    if accounts.is_empty() {
        info!("No accounts found in Redis. Nothing to sync.");
        return Ok(());
    }

    pg_client
        .batch_execute("TRUNCATE TABLE accounts_sync_stage;")
        .await?;
    info!("cleared staging table");

    let mut copy_payload_buffer = String::with_capacity(accounts.len().saturating_mul(160));
    let mut skipped = 0;

    for (id_str, json_str) in accounts {
        // Deserialize the JSON Value
        let data: AccountData = match serde_json::from_str(&json_str) {
            Ok(d) => d,
            Err(e) => {
                error!(
                    "Skipping: Failed to parse JSON for account {}: {}",
                    id_str, e
                );
                skipped += 1;
                continue;
            }
        };

        // Write one tab-delimited row for PostgreSQL COPY text format.
        let _ = writeln!(
            &mut copy_payload_buffer,
            "{}\t{}\t{}\t{}\t{}\t{}",
            &id_str,
            &data.account_name,
            to_pg_text_array_literal(&data.positions),
            data.can_short,
            &data.created_at,
            &data.updated_at,
        );
    }

    info!("created copy payload buffer");

    if copy_payload_buffer.is_empty() {
        info!(
            "No valid account rows to copy (skipped {}). Sync completed with no writes.",
            skipped
        );
        return Ok(());
    }

    let copy_query = "COPY accounts_sync_stage (account_id, account_name, positions, can_short, created_at, updated_at) FROM STDIN WITH (FORMAT text, DELIMITER '\t', NULL '\\N')";

    match pg_client.copy_in(copy_query).await {
        Ok(sink) => {
            tokio::pin!(sink);

            let chunk = Bytes::from(copy_payload_buffer);
            sink.send(chunk).await?;
            sink.close().await?;

            info!("copied accounts into staging table");

            let upserted = pg_client.execute(
                    "INSERT INTO accounts (account_id, account_name, positions, can_short, created_at, updated_at)
                     SELECT account_id, account_name, positions, can_short, created_at, updated_at
                     FROM accounts_sync_stage
                     ON CONFLICT (account_id) DO UPDATE SET
                        account_name = EXCLUDED.account_name,
                        positions = EXCLUDED.positions,
                        can_short = EXCLUDED.can_short,
                        updated_at = EXCLUDED.updated_at",
                    &[],
                )
                .await?;

            if skipped > 0 {
                warn!("skipped {} malformed account payloads from Redis", skipped);
            }
            info!("upserted {} accounts to postgres", upserted);
        }
        Err(e) => {
            error!("Failed to initialize Postgres COPY context: {}", e);
        }
    }
    Ok(())
}

fn to_pg_text_array_literal(values: &[String]) -> String {
    if values.is_empty() {
        return "{}".to_string();
    }

    let elements: Vec<String> = values
        .iter()
        .map(|val| {
            let mut escaped = String::with_capacity(val.len() + 2);
            escaped.push('"');
            for ch in val.chars() {
                match ch {
                    '\\' => escaped.push_str("\\\\"),
                    '"' => escaped.push_str("\\\""),
                    _ => escaped.push(ch),
                }
            }
            escaped.push('"');
            escaped
        })
        .collect();

    format!("{{{}}}", elements.join(","))
}
