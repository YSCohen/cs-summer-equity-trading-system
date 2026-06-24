//! Copy users, accounts, and positions from postgres back to redis dictionaries

use dotenvy::dotenv;
use serde::Serialize;
use std::env;
use std::error::Error;
use tokio_postgres::NoTls;
use tracing::{debug, error, info, warn};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    info!("=== STARTING POSTGRES -> REDIS WRITER ===");

    // Run the main pipeline and catch any fatal initialization errors
    if let Err(err) = run().await {
        error!(%err, "Fatal application initialization error");
        std::process::exit(1);
    }
}

async fn run() -> Result<(), Box<dyn Error>> {
    let _ = dotenv();

    let pg_config = env::var("POSTGRES_CONFIG").map_err(|_| "POSTGRES_CONFIG must be set")?;
    let redis_url = env::var("REDIS_URL").map_err(|_| "REDIS_URL must be set")?;

    debug!("read env vars");

    // Connect to postgres
    let (pg_client, connection) = tokio_postgres::connect(&pg_config, NoTls).await?;
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            error!("postgres connection driver error: {}", e);
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

struct PgToRedisSyncSpec<T> {
    entity_name: &'static str,
    redis_key: &'static str,
    select_sql: &'static str,
    parse_row: fn(&tokio_postgres::Row) -> Result<(String, T), String>,
}

async fn sync_table_to_redis<T: Serialize>(
    pg_client: &tokio_postgres::Client,
    redis_conn: &mut redis::aio::MultiplexedConnection,
    spec: PgToRedisSyncSpec<T>,
) -> Result<(), Box<dyn Error + 'static>> {
    debug!("fetching {} from postgres...", spec.entity_name);

    let rows = pg_client.query(spec.select_sql, &[]).await?;

    info!("found {} {} in postgres", rows.len(), spec.entity_name);

    if rows.is_empty() {
        info!(
            "nothing to sync, wiping empty redis key \"{}\"",
            spec.redis_key
        );
        let _: () = redis::cmd("DEL")
            .arg(spec.redis_key)
            .query_async(&mut *redis_conn)
            .await?;
        return Ok(());
    }

    let mut pipe = redis::pipe();
    pipe.atomic(); // Guarantees the DEL and subsequent HSETs happen in one isolated tick

    // Wiping the hash first ensures deleted Postgres records are purged from Redis
    pipe.cmd("DEL").arg(spec.redis_key).ignore();

    let mut skipped = 0;
    let mut queued_writes = 0;

    for row in rows {
        let (id_str, entity_data) = match (spec.parse_row)(&row) {
            Ok(res) => res,
            Err(err) => {
                error!("Skipping row: {}", err);
                skipped += 1;
                continue;
            }
        };

        let json_str = match serde_json::to_string(&entity_data) {
            Ok(j) => j,
            Err(err) => {
                error!(
                    "Failed to serialize {} {}: {}",
                    spec.entity_name, id_str, err
                );
                skipped += 1;
                continue;
            }
        };

        pipe.cmd("HSET")
            .arg(spec.redis_key)
            .arg(id_str)
            .arg(json_str)
            .ignore();

        queued_writes += 1;
    }

    if queued_writes > 0 {
        let _: () = pipe.query_async(&mut *redis_conn).await?;
        if skipped > 0 {
            warn!("skipped {} unparseable {} rows", skipped, spec.entity_name);
        }
        info!(
            "atomically wrote {} {} to redis key \"{}\"",
            queued_writes, spec.entity_name, spec.redis_key
        );
    } else {
        warn!("no valid {} rows were queued for redis", spec.entity_name);
    }

    Ok(())
}

// --- Safe Row-Extraction Helpers ---

fn get_opt_str(row: &tokio_postgres::Row, idx: usize) -> Result<String, String> {
    row.try_get::<usize, Option<String>>(idx)
        .map(|opt| opt.unwrap_or_default())
        .map_err(|e| format!("failed to read string at col {idx}: {e}"))
}

fn get_opt_vec_str(row: &tokio_postgres::Row, idx: usize) -> Result<Vec<String>, String> {
    row.try_get::<usize, Option<Vec<String>>>(idx)
        .map(|opt| opt.unwrap_or_default())
        .map_err(|e| format!("failed to read string array at col {idx}: {e}"))
}

// --- Implementations ---

#[derive(Serialize)]
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
    sync_table_to_redis(
        pg_client,
        redis_conn,
        PgToRedisSyncSpec {
            entity_name: "users",
            redis_key: "users",
            select_sql: "SELECT user_id::text, username, oauth_key, accounts_associated::text[], created_at::text, updated_at::text FROM users",
            parse_row: |row| {
                let id: String = row.try_get::<usize, Option<String>>(0)
                    .map_err(|e| e.to_string())?
                    .ok_or_else(|| "user_id is null".to_string())?;

                Ok((id, User {
                    username: get_opt_str(row, 1)?,
                    oauth_key: get_opt_str(row, 2)?,
                    accounts_associated: get_opt_vec_str(row, 3)?,
                    created_at: get_opt_str(row, 4)?,
                    updated_at: get_opt_str(row, 5)?,
                }))
            }
        }
    ).await
}

#[derive(Serialize)]
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
    sync_table_to_redis(
        pg_client,
        redis_conn,
        PgToRedisSyncSpec {
            entity_name: "accounts",
            redis_key: "accounts",
            select_sql: "SELECT account_id::text, account_name, positions::text[], can_short, created_at::text, updated_at::text FROM accounts",
            parse_row: |row| {
                let id: String = row.try_get::<usize, Option<String>>(0)
                    .map_err(|e| e.to_string())?
                    .ok_or_else(|| "account_id is null".to_string())?;

                let can_short: bool = row.try_get::<usize, Option<bool>>(3)
                    .map_err(|e| e.to_string())?
                    .unwrap_or(false);

                Ok((id, Account {
                    account_name: get_opt_str(row, 1)?,
                    positions: get_opt_vec_str(row, 2)?,
                    can_short,
                    created_at: get_opt_str(row, 4)?,
                    updated_at: get_opt_str(row, 5)?,
                }))
            }
        }
    ).await
}

#[derive(Serialize)]
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
    sync_table_to_redis(
        pg_client,
        redis_conn,
        PgToRedisSyncSpec {
            entity_name: "positions",
            redis_key: "positions",
            select_sql: "SELECT position_id::text, account_id::text, symbol_ticker, quantity, created_at::text, updated_at::text FROM positions",
            parse_row: |row| {
                let id: String = row.try_get::<usize, Option<String>>(0)
                    .map_err(|e| e.to_string())?
                    .ok_or_else(|| "position_id is null".to_string())?;

                let quantity: i32 = row.try_get::<usize, Option<i32>>(3)
                    .map_err(|e| e.to_string())?
                    .unwrap_or(0);

                Ok((id, Position {
                    account_id: get_opt_str(row, 1)?,
                    symbol_ticker: get_opt_str(row, 2)?,
                    quantity,
                    created_at: get_opt_str(row, 4)?,
                    updated_at: get_opt_str(row, 5)?,
                }))
            }
        }
    ).await
}
