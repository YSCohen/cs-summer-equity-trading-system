//! copy users, accounts, positions from redis to postgres

use bytes::Bytes;
use dotenvy::dotenv;
use futures_util::SinkExt;
use std::env;
use std::error::Error;
use std::fmt::Write;
use tokio_postgres::NoTls;
use tracing::{debug, error, info, warn};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    info!("=== STARTING DB SYNCER ===");

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

    debug!("read env vars");

    // Connect to postgres
    let (pg_client, connection) = tokio_postgres::connect(&pg_config, NoTls).await?;
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            error!("PostgreSQL connection driver error: {}", e);
        }
    });
    debug!("connected to postgres");

    // Connect to redis
    let redis_client = redis::Client::open(redis_url)?;
    let mut redis_conn = redis_client.get_multiplexed_async_connection().await?;
    debug!("connected to redis");

    sync_users(&pg_client, &mut redis_conn).await?;
    sync_accounts(&pg_client, &mut redis_conn).await?;
    sync_positions(&pg_client, &mut redis_conn).await?;

    Ok(())
}

#[derive(serde::Deserialize)]
struct User {
    username: String,
    oauth_key: String,
    accounts_associated: Vec<String>,
    created_at: String,
    updated_at: String,
}

async fn sync_users(
    pg_client: &tokio_postgres::Client,
    redis_conn: &mut redis::aio::MultiplexedConnection,
) -> Result<(), Box<dyn Error + 'static>> {
    let table_name = "users";
    let staging_table_name = "users_sync_stage";

    debug!("sync users...");

    let users: std::collections::HashMap<String, String> = redis::cmd("HGETALL")
        .arg(table_name)
        .query_async(&mut *redis_conn)
        .await?;

    info!(
        "found {} users in redis dictionary \"{}\"",
        users.len(),
        table_name
    );
    if users.is_empty() {
        info!("nothing to sync");
        return Ok(());
    }

    pg_client
        .execute("TRUNCATE TABLE $1;", &[&staging_table_name])
        .await?;

    debug!("cleared table {}", staging_table_name);

    let mut copy_payload_buffer = String::with_capacity(users.len() * 200);
    let mut skipped = 0;

    for (id_str, json_str) in users {
        // Deserialize the JSON Value
        let data: User = match serde_json::from_str(&json_str) {
            Ok(d) => d,
            Err(e) => {
                error!("Skipping: Failed to parse JSON for user {}: {}", id_str, e);
                skipped += 1;
                continue;
            }
        };

        // Write one tab-delimited row for PostgreSQL COPY text format.
        let _ = writeln!(
            &mut copy_payload_buffer,
            "{}\t{}\t{}\t{}\t{}\t{}",
            id_str,
            data.username,
            data.oauth_key,
            to_pg_text_array_literal(&data.accounts_associated),
            data.created_at,
            data.updated_at,
        );
    }

    debug!("created copy payload buffer");

    if copy_payload_buffer.is_empty() {
        info!(
            "No valid user rows to copy (skipped {}). Sync completed with no writes.",
            skipped
        );
        return Ok(());
    }

    // this _is_ safe, because i set the staging_table_name var myself
    let copy_query = format!(
        "COPY {} (user_id, username, oauth_key, accounts_associated, created_at, updated_at) FROM STDIN WITH (FORMAT text, DELIMITER '\t', NULL '\\N')",
        staging_table_name
    );

    match pg_client.copy_in(&copy_query).await {
        Ok(sink) => {
            tokio::pin!(sink);

            let chunk = Bytes::from(copy_payload_buffer);
            sink.send(chunk).await?;
            sink.close().await?;

            info!("wrote users into staging table");

            let upserted = pg_client.execute(
                    "INSERT INTO $1 (user_id, username, oauth_key, accounts_associated, created_at, updated_at)
                     SELECT user_id, username, oauth_key, accounts_associated, created_at, updated_at
                     FROM $2
                     ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        oauth_key = EXCLUDED.oauth_key,
                        accounts_associated = EXCLUDED.accounts_associated,
                        updated_at = EXCLUDED.updated_at",
                    &[&table_name, &staging_table_name],
                )
                .await?;

            if skipped > 0 {
                warn!("skipped {} malformed user payloads from redis", skipped);
            }

            info!("upserted {} users to {} table", upserted, table_name);
        }
        Err(e) => {
            error!("failed to initialize postgres COPY context: {}", e);
        }
    }
    Ok(())
}

#[derive(serde::Deserialize)]
struct Account {
    account_name: String,
    positions: Vec<String>,
    can_short: bool,
    created_at: String,
    updated_at: String,
}

async fn sync_accounts(
    pg_client: &tokio_postgres::Client,
    redis_conn: &mut redis::aio::MultiplexedConnection,
) -> Result<(), Box<dyn Error + 'static>> {
    let table_name = "accounts";
    let staging_table_name = "accounts_sync_stage";

    debug!("sync accounts...");

    let accounts: std::collections::HashMap<String, String> = redis::cmd("HGETALL")
        .arg(table_name)
        .query_async(&mut *redis_conn)
        .await?;

    info!(
        "found {} accounts in redis dictionary \"{}\"",
        accounts.len(),
        table_name
    );
    if accounts.is_empty() {
        info!("nothing to sync");
        return Ok(());
    }

    pg_client
        .execute("TRUNCATE TABLE $1;", &[&staging_table_name])
        .await?;

    debug!("cleared table {}", staging_table_name);

    let mut copy_payload_buffer = String::with_capacity(accounts.len() * 200);
    let mut skipped = 0;

    for (id_str, json_str) in accounts {
        // Deserialize the JSON Value
        let data: Account = match serde_json::from_str(&json_str) {
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
            id_str,
            data.account_name,
            to_pg_text_array_literal(&data.positions),
            data.can_short,
            data.created_at,
            data.updated_at,
        );
    }

    debug!("created copy payload buffer");

    if copy_payload_buffer.is_empty() {
        info!(
            "No valid account rows to copy (skipped {}). Sync completed with no writes.",
            skipped
        );
        return Ok(());
    }

    // this _is_ safe, because i set the staging_table_name var myself
    let copy_query = format!(
        "COPY {} (account_id, account_name, positions, can_short, created_at, updated_at) FROM STDIN WITH (FORMAT text, DELIMITER '\t', NULL '\\N')",
        staging_table_name
    );

    match pg_client.copy_in(&copy_query).await {
        Ok(sink) => {
            tokio::pin!(sink);

            let chunk = Bytes::from(copy_payload_buffer);
            sink.send(chunk).await?;
            sink.close().await?;

            info!("wrote accounts into staging table");

            let upserted = pg_client.execute(
                    "INSERT INTO $1 (account_id, account_name, positions, can_short, created_at, updated_at)
                     SELECT account_id, account_name, positions, can_short, created_at, updated_at
                     FROM $2
                     ON CONFLICT (account_id) DO UPDATE SET
                        account_name = EXCLUDED.account_name,
                        positions = EXCLUDED.positions,
                        can_short = EXCLUDED.can_short,
                        updated_at = EXCLUDED.updated_at",
                    &[&table_name, &staging_table_name],
                )
                .await?;

            if skipped > 0 {
                warn!("skipped {} malformed account payloads from redis", skipped);
            }

            info!("upserted {} accounts to {} table", upserted, table_name);
        }
        Err(e) => {
            error!("failed to initialize postgres COPY context: {}", e);
        }
    }
    Ok(())
}

#[derive(serde::Deserialize)]
struct Position {
    account_id: String,
    symbol_ticker: String,
    quantity: i32,
    created_at: String,
    updated_at: String,
}

async fn sync_positions(
    pg_client: &tokio_postgres::Client,
    redis_conn: &mut redis::aio::MultiplexedConnection,
) -> Result<(), Box<dyn Error + 'static>> {
    let table_name = "positions";
    let staging_table_name = "positions_sync_stage";

    debug!("sync positions...");

    let positions: std::collections::HashMap<String, String> = redis::cmd("HGETALL")
        .arg(table_name)
        .query_async(&mut *redis_conn)
        .await?;

    info!(
        "found {} positions in redis dictionary \"{}\"",
        positions.len(),
        table_name
    );
    if positions.is_empty() {
        info!("nothing to sync");
        return Ok(());
    }

    pg_client
        .execute("TRUNCATE TABLE $1;", &[&staging_table_name])
        .await?;

    debug!("cleared table {}", staging_table_name);

    let mut copy_payload_buffer = String::with_capacity(positions.len() * 200);
    let mut skipped = 0;

    for (id_str, json_str) in positions {
        // Deserialize the JSON Value
        let data: Position = match serde_json::from_str(&json_str) {
            Ok(d) => d,
            Err(e) => {
                error!(
                    "Skipping: Failed to parse JSON for position {}: {}",
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
            id_str,
            data.account_id,
            data.symbol_ticker,
            data.quantity,
            data.created_at,
            data.updated_at,
        );
    }

    debug!("created copy payload buffer");

    if copy_payload_buffer.is_empty() {
        info!(
            "No valid position rows to copy (skipped {}). Sync completed with no writes.",
            skipped
        );
        return Ok(());
    }

    // this _is_ safe, because i set the staging_table_name var myself
    let copy_query = format!(
        "COPY {} (position_id, account_id, symbol_ticker, quantity, created_at, updated_at) FROM STDIN WITH (FORMAT text, DELIMITER '\t', NULL '\\N')",
        staging_table_name
    );

    match pg_client.copy_in(&copy_query).await {
        Ok(sink) => {
            tokio::pin!(sink);

            let chunk = Bytes::from(copy_payload_buffer);
            sink.send(chunk).await?;
            sink.close().await?;

            info!("wrote accounts into staging table");

            let upserted = pg_client.execute(
                    "INSERT INTO $1 (position_id, account_id, symbol_ticker, quantity, created_at, updated_at)
                     SELECT position_id, account_id, symbol_ticker, quantity, created_at, updated_at
                     FROM $2
                     ON CONFLICT (position_id) DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        updated_at = EXCLUDED.updated_at",
                    &[&table_name, &staging_table_name],
                )
                .await?;

            if skipped > 0 {
                warn!("skipped {} malformed position payloads from redis", skipped);
            }

            info!("upserted {} positions to {} table", upserted, table_name);
        }
        Err(e) => {
            error!("failed to initialize postgres COPY context: {}", e);
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
