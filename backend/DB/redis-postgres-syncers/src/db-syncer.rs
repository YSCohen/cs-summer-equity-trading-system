//! copy positions, accounts, users from redis to postgres

use bytes::Bytes;
use dotenvy::dotenv;
use futures_util::SinkExt;
use std::env;
use std::error::Error;
use std::fmt::Write;
use tokio_postgres::NoTls;
use tracing::{error, info};

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
        .batch_execute(
            "DROP TABLE IF EXISTS accounts_sync_stage;
             CREATE TEMP TABLE accounts_sync_stage (
                account_id UUID PRIMARY KEY,
                account_name TEXT,
                positions UUID[],
                can_short BOOLEAN,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
             ) ON COMMIT DROP;",
        )
        .await?;
    info!("created temporary staging table for account COPY");

    let mut copy_payload_buffer = String::with_capacity(accounts.len().saturating_mul(160));
    let mut skipped = 0usize;

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

        let positions_literal = to_pg_text_array_literal(&data.positions);

        // Write one tab-delimited row for PostgreSQL COPY text format.
        let _ = writeln!(
            &mut copy_payload_buffer,
            "{}\t{}\t{}\t{}\t{}\t{}",
            escape_copy_text_field(&id_str),
            escape_copy_text_field(&data.account_name),
            escape_copy_text_field(&positions_literal),
            data.can_short,
            escape_copy_text_field(&data.created_at),
            escape_copy_text_field(&data.updated_at),
        );
    }

    if copy_payload_buffer.is_empty() {
        info!(
            "No valid account rows to copy (skipped {}). Sync completed with no writes.",
            skipped
        );
        return Ok(());
    }

    let copy_query = "COPY accounts_sync_stage (account_id, account_name, positions, can_short, created_at, updated_at) FROM STDIN WITH (FORMAT text, DELIMITER '\t', NULL '\\N')";

    let sink = pg_client.copy_in(copy_query).await?;
    tokio::pin!(sink);

    let chunk = Bytes::from(copy_payload_buffer);
    sink.send(chunk).await?;
    sink.close().await?;

    let upserted = pg_client
        .execute(
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
        info!("Skipped {} malformed account payloads from Redis", skipped);
    }

    info!("copied and upserted {} accounts to postgres", upserted);

    Ok(())
}

fn escape_copy_text_field(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len());

    for ch in value.chars() {
        match ch {
            '\\' => escaped.push_str("\\\\"),
            '\t' => escaped.push_str("\\t"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            _ => escaped.push(ch),
        }
    }

    escaped
}

fn to_pg_text_array_literal(values: &[String]) -> String {
    if values.is_empty() {
        return "{}".to_string();
    }

    let mut literal = String::from("{");

    for (index, value) in values.iter().enumerate() {
        if index > 0 {
            literal.push(',');
        }

        literal.push('"');
        for ch in value.chars() {
            match ch {
                '\\' => literal.push_str("\\\\"),
                '"' => literal.push_str("\\\""),
                _ => literal.push(ch),
            }
        }
        literal.push('"');
    }

    literal.push('}');
    literal
}
