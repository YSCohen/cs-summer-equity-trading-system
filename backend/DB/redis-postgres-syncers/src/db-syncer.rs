//! copy positions, accounts, users from redis to postgres

use dotenvy::dotenv;
use std::env;
use std::error::Error;
use tokio_postgres::NoTls;
use tracing::{debug, error, info};

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

    debug!("read env vars");

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
    debug!(
        "Found {} accounts in Redis. Starting migration...",
        accounts.len()
    );

    let stmt = pg_client.prepare(
        "INSERT INTO accounts (account_id, account_name, positions, can_short, created_at, updated_at) 
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (account_id) DO UPDATE SET
            account_name = EXCLUDED.account_name,
            positions = EXCLUDED.positions,
            can_short = EXCLUDED.can_short,
            updated_at = EXCLUDED.updated_at"
    ).await?;
    debug!("prepared sql statement in postgres");

    for (id_str, json_str) in accounts {
        // Deserialize the JSON Value
        let data: AccountData = match serde_json::from_str(&json_str) {
            Ok(d) => d,
            Err(e) => {
                error!(
                    "Skipping: Failed to parse JSON for account {}: {}",
                    id_str, e
                );
                continue;
            }
        };

        // Execute the Postgres insert
        match pg_client
            .execute(
                &stmt,
                &[
                    &id_str,
                    &data.account_name,
                    &data.positions,
                    &data.can_short,
                    &data.created_at,
                    &data.updated_at,
                ],
            )
            .await
        {
            Ok(_) => info!("Successfully migrated account {}", id_str),
            Err(e) => error!("Failed to insert account {} into Postgres: {}", id_str, e),
        }
    }
    info!("copied accounts to postgres");

    Ok(())
}
