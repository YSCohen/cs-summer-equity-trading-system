//! copy users, accounts, positions from redis to postgres

use bytes::Bytes;
use dotenvy::dotenv;
use futures_util::SinkExt;
use serde::de::DeserializeOwned;
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

struct JsonHashTableSyncSpec<T> {
    entity_name: &'static str,
    redis_key: &'static str,
    staging_table_name: &'static str,
    target_table_name: &'static str,
    copy_columns: &'static str,
    conflict_column: &'static str,
    update_assignments: &'static str,
    parse_row: fn(&str, &str) -> Result<T, String>,
    format_row: fn(&str, &T) -> String,
}

fn parse_json_row<T: DeserializeOwned>(
    entity_name: &str,
    id: &str,
    json_str: &str,
) -> Result<T, String> {
    serde_json::from_str(json_str)
        .map_err(|err| format!("Skipping: Failed to parse JSON for {entity_name} {id}: {err}"))
}

fn build_upsert_sql(
    target_table_name: &str,
    staging_table_name: &str,
    copy_columns: &str,
    conflict_column: &str,
    update_assignments: &str,
) -> String {
    format!(
        "INSERT INTO {target_table_name} ({copy_columns})
  SELECT {copy_columns}
  FROM {staging_table_name}
  ON CONFLICT ({conflict_column}) DO UPDATE SET
    {update_assignments}"
    )
}

async fn sync_json_hash_table<T>(
    pg_client: &tokio_postgres::Client,
    redis_conn: &mut redis::aio::MultiplexedConnection,
    spec: JsonHashTableSyncSpec<T>,
) -> Result<(), Box<dyn Error + 'static>> {
    debug!("sync {}...", spec.entity_name);

    let rows: std::collections::HashMap<String, String> = redis::cmd("HGETALL")
        .arg(spec.redis_key)
        .query_async(&mut *redis_conn)
        .await?;

    info!(
        "found {} {} in redis key \"{}\"",
        rows.len(),
        spec.entity_name,
        spec.redis_key
    );
    if rows.is_empty() {
        info!("nothing to sync");
        return Ok(());
    }

    pg_client
        .execute(&format!("TRUNCATE TABLE {};", spec.staging_table_name), &[])
        .await?;

    debug!("cleared table {}", spec.staging_table_name);

    let mut copy_payload_buffer = String::with_capacity(rows.len() * 200);
    let mut skipped = 0;

    for (id_str, json_str) in rows {
        let data = match (spec.parse_row)(&id_str, &json_str) {
            Ok(data) => data,
            Err(err) => {
                error!("{}", err);
                skipped += 1;
                continue;
            }
        };

        let _ = writeln!(
            &mut copy_payload_buffer,
            "{}",
            (spec.format_row)(&id_str, &data)
        );
    }

    debug!("created copy payload buffer");

    if copy_payload_buffer.is_empty() {
        info!(
            "No valid {} rows to copy (skipped {}). Sync completed with no writes.",
            spec.entity_name, skipped
        );
        return Ok(());
    }

    let copy_query = format!(
        "COPY {} ({}) FROM STDIN WITH (FORMAT text, DELIMITER '\t', NULL '\\N')",
        spec.staging_table_name, spec.copy_columns
    );

    match pg_client.copy_in(&copy_query).await {
        Ok(sink) => {
            tokio::pin!(sink);

            let chunk = Bytes::from(copy_payload_buffer);
            sink.send(chunk).await?;
            sink.close().await?;

            info!("wrote {} into staging table", spec.entity_name);

            let upserted = pg_client
                .execute(
                    &build_upsert_sql(
                        spec.target_table_name,
                        spec.staging_table_name,
                        spec.copy_columns,
                        spec.conflict_column,
                        spec.update_assignments,
                    ),
                    &[],
                )
                .await?;

            if skipped > 0 {
                warn!(
                    "skipped {} malformed {} payloads from redis",
                    skipped, spec.entity_name
                );
            }

            info!(
                "upserted {} {} to {} table",
                upserted, spec.entity_name, spec.target_table_name
            );
        }
        Err(err) => {
            error!("failed to initialize postgres COPY context: {}", err);
        }
    }

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
    sync_json_hash_table(
        pg_client,
        redis_conn,
        JsonHashTableSyncSpec {
            entity_name: "users",
            redis_key: "users",
            staging_table_name: "users_sync_stage",
            target_table_name: "users",
            copy_columns: "user_id, username, oauth_key, accounts_associated, created_at, updated_at",
            conflict_column: "user_id",
            update_assignments: "username = EXCLUDED.username,\n    oauth_key = EXCLUDED.oauth_key,\n    accounts_associated = EXCLUDED.accounts_associated,\n    updated_at = EXCLUDED.updated_at",
            parse_row: |id, json| parse_json_row::<User>("user", id, json),
            format_row: |id, data| {
                format!(
                    "{}\t{}\t{}\t{}\t{}\t{}",
                    id,
                    data.username,
                    data.oauth_key,
                    to_pg_text_array_literal(&data.accounts_associated),
                    data.created_at,
                    data.updated_at,
                )
            },
        },
    )
    .await
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
    sync_json_hash_table(
        pg_client,
        redis_conn,
        JsonHashTableSyncSpec {
            entity_name: "accounts",
            redis_key: "accounts",
            staging_table_name: "accounts_sync_stage",
            target_table_name: "accounts",
            copy_columns: "account_id, account_name, positions, can_short, created_at, updated_at",
            conflict_column: "account_id",
            update_assignments: "account_name = EXCLUDED.account_name,\n    positions = EXCLUDED.positions,\n    can_short = EXCLUDED.can_short,\n    updated_at = EXCLUDED.updated_at",
            parse_row: |id, json| parse_json_row::<Account>("account", id, json),
            format_row: |id, data| {
                format!(
                    "{}\t{}\t{}\t{}\t{}\t{}",
                    id,
                    data.account_name,
                    to_pg_text_array_literal(&data.positions),
                    data.can_short,
                    data.created_at,
                    data.updated_at,
                )
            },
        },
    )
    .await
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
    sync_json_hash_table(
        pg_client,
        redis_conn,
        JsonHashTableSyncSpec {
            entity_name: "positions",
            redis_key: "positions",
            staging_table_name: "positions_sync_stage",
            target_table_name: "positions",
            copy_columns: "position_id, account_id, symbol_ticker, quantity, created_at, updated_at",
            conflict_column: "position_id",
            update_assignments: "quantity = EXCLUDED.quantity,\n    updated_at = EXCLUDED.updated_at",
            parse_row: |id, json| parse_json_row::<Position>("position", id, json),
            format_row: |id, data| {
                format!(
                    "{}\t{}\t{}\t{}\t{}\t{}",
                    id,
                    data.account_id,
                    data.symbol_ticker,
                    data.quantity,
                    data.created_at,
                    data.updated_at,
                )
            },
        },
    )
    .await
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
