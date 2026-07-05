//! Write trades from redis stream (sent by API) to postgres

use dotenvy::dotenv;
use futures_util::SinkExt;
use redis::AsyncCommands;
use redis::streams::{
    StreamDeletionPolicy, StreamReadOptions, StreamReadReply, StreamTrimOptions, StreamTrimmingMode,
};
use serde::Deserialize;
use std::env;
use std::fmt::Write;
use tokio_postgres::NoTls;
use tracing::{debug, error, info, warn};

#[tokio::main]
async fn main() {
    let _ = dotenv();

    if let Err(err) = helpers::init_tracing("trade-writer") {
        eprintln!("failed to initialize tracing: {:?}", err);
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        std::process::exit(1);
    }

    info!("=== STARTING TRADE WRITER ===");

    // Run the main pipeline and catch any fatal initialization errors
    if let Err(err) = run().await {
        error!(?err, "Fatal application initialization error");
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        std::process::exit(1);
    }
}

async fn run() -> Result<(), Box<dyn std::error::Error>> {
    let pg_config = env::var("POSTGRES_CONFIG").map_err(|_| "POSTGRES_CONFIG must be set")?;
    let redis_url = env::var("REDIS_URL").map_err(|_| "REDIS_URL must be set")?;
    let stream_name = env::var("REDIS_STREAM_NAME").map_err(|_| "REDIS_STREAM_NAME must be set")?;
    let consumer_group =
        env::var("REDIS_CONSUMER_GROUP").map_err(|_| "REDIS_CONSUMER_GROUP must be set")?;
    let worker_name = env::var("WORKER_NAME").map_err(|_| "WORKER_NAME must be set")?;

    debug!("read env vars");

    // Connect to postgres
    let (pg_client, connection) = tokio_postgres::connect(&pg_config, NoTls).await?;
    tokio::spawn(async move {
        if let Err(e) = connection.await {
            error!(?e, "PostgreSQL connection driver error");
        }
    });
    debug!("connected to postgres");

    // Connect to redis
    let redis_client = redis::Client::open(redis_url)?;
    let mut redis_conn = redis_client.get_multiplexed_async_connection().await?;
    debug!("connected to redis");

    // Create Redis Consumer Group dynamically
    let group_create_result: Result<(), redis::RedisError> = redis_conn
        .xgroup_create_mkstream(&stream_name, &consumer_group, "0")
        .await;

    if let Err(e) = group_create_result {
        if e.to_string().contains("BUSYGROUP") {
            debug!("Consumer group '{}' already exists", consumer_group);
        } else {
            error!(?e, "Initializing consumer group failed");
        }
    }

    info!("Pipeline engaged for stream '{}'", stream_name);

    // start by processing pending messages ("0"), switch to new messages (">") later
    let mut stream_id = "0".to_string();

    // buffer to hold bulk COPY data. Pre-allocating ~500KB to avoid reallocations
    let mut copy_payload_buffer = String::with_capacity(512_000);

    // opts to fetch batches from the configured redis stream
    let opts = StreamReadOptions::default()
        .group(&consumer_group, &worker_name)
        .count(5000) // TODO: determine best number
        .block(100);

    loop {
        // (these two vars need to be assigned because of lifetime witchcraft in the select macro)
        let stream_name_arr = [&stream_name];
        let stream_id_arr = [&stream_id];

        // Select between waiting for Redis stream entries or a shutdown signal:
        let reply: StreamReadReply = tokio::select! {
            res = redis_conn.xread_options(&stream_name_arr, &stream_id_arr, &opts) => {
                match res {
                    Ok(r) => r,
                    Err(e) => {
                        error!(?e, "Redis stream read failed");
                        tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
                        std::process::exit(1);
                    }
                }
            }
            () = helpers::shutdown_signal() => {
                info!("Shutdown signal received. Exiting loop gracefully...");
                return Ok(());
            }
        };

        if reply.keys.is_empty() || reply.keys[0].ids.is_empty() {
            if stream_id == "0" {
                info!("Finished processing pending entries, switching to new messages.");
                stream_id = ">".to_string();
            }
            continue;
        }

        let msg_ids = build_payload_buffer(&mut copy_payload_buffer, reply);

        // If we parsed 0 valid rows but have msg_ids, we must ACK them so they don't get stuck.
        if copy_payload_buffer.is_empty() {
            warn!(
                "Decoded no valid rows, ACKing {} bad messages to discard them.",
                msg_ids.len()
            );
            if let Err(e) =
                ack_and_trim_stream(&mut redis_conn, &stream_name, &consumer_group, &msg_ids).await
            {
                error!(?e, "Failed to ACK and trim bad messages in Redis");
            }
            continue;
        }

        let copy_query = "COPY trades (trade_id, account_id, user_id, direction, symbol_ticker, created_at, updated_at, quantity, price, other_account) FROM STDIN WITH (FORMAT text, DELIMITER '\t', NULL '\\N')";

        match pg_client.copy_in(copy_query).await {
            Ok(sink) => {
                tokio::pin!(sink);

                // Send the entire batch over the network in one chunk
                let chunk = bytes::Bytes::from(copy_payload_buffer.clone());

                // If sending/closing fails, abort transaction and DO NOT ACK
                if let Err(e) = sink.send(chunk).await {
                    log_postgres_error("Streaming COPY failed (transaction aborted)", &e);
                    continue;
                }

                if let Err(e) = sink.close().await {
                    log_postgres_error("Finalizing COPY failed (transaction aborted)", &e);
                    continue;
                }

                // xack and trim messages in redis ONLY after postgres confirms write
                match ack_and_trim_stream(&mut redis_conn, &stream_name, &consumer_group, &msg_ids)
                    .await
                {
                    Ok(()) => info!(
                        "Successfully copied, ACK'd, and trimmed {} rows",
                        msg_ids.len()
                    ),
                    Err(e) => error!(?e, "Failed to ACK and trim messages in Redis"),
                }
            }
            Err(e) => {
                error!(?e, "Failed to initialize postgres COPY context");
            }
        }
    }
}

fn build_payload_buffer(copy_payload_buffer: &mut String, reply: StreamReadReply) -> Vec<String> {
    let mut msg_ids = Vec::new();
    copy_payload_buffer.clear(); // Clear the buffer for the new batch

    for stream_key in reply.keys {
        for record in stream_key.ids {
            msg_ids.push(record.id.clone());

            let Some(redis::Value::BulkString(bytes)) = record.map.get("d") else {
                warn!("Redis message {} missing binary field 'd'", record.id);
                continue; // Skip malformed record
            };

            let trade: TradePayload = match rmp_serde::from_slice(bytes) {
                Ok(t) => t,
                Err(e) => {
                    warn!(?e, "Failed to decode payload for {}", record.id);
                    continue; // Skip badly serialized record
                }
            };

            let created = jiff::Timestamp::from_second(trade.created_at).map_or_else(
                |_| "\\N".to_string(),
                |z| z.strftime("%Y-%m-%d %H:%M:%S").to_string(),
            );

            let updated = jiff::Timestamp::from_second(trade.updated_at).map_or_else(
                |_| "\\N".to_string(),
                |z| z.strftime("%Y-%m-%d %H:%M:%S").to_string(),
            );

            let other_acc = trade
                .other_account
                .as_deref()
                .filter(|value| !value.is_empty())
                .unwrap_or("\\N");

            let _ = writeln!(
                copy_payload_buffer,
                "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}",
                trade.trade_id,
                trade.account_id,
                trade.user_id,
                trade.direction,
                trade.symbol_ticker,
                created,
                updated,
                trade.quantity,
                trade.price,
                other_acc
            );
        }
    }

    msg_ids
}

#[derive(Deserialize)]
struct TradePayload {
    trade_id: String,
    account_id: String,
    user_id: String,
    direction: String,
    symbol_ticker: String,
    created_at: i64,
    updated_at: i64,
    quantity: i32,
    price: String,
    other_account: Option<String>,
}

fn log_postgres_error(context: &str, err: &tokio_postgres::Error) {
    if let Some(db_error) = err.as_db_error() {
        error!(?db_error, "{}", context);
    } else {
        error!(?err, "{}", context);
    }
}

async fn ack_and_trim_stream(
    redis_conn: &mut redis::aio::MultiplexedConnection,
    stream_name: &str,
    consumer_group: &str,
    msg_ids: &[String],
) -> Result<(), redis::RedisError> {
    let _: usize = redis_conn
        .xack(stream_name, consumer_group, msg_ids)
        .await?;

    let _: usize = redis_conn
        .xtrim_options(
            stream_name,
            &StreamTrimOptions::maxlen(StreamTrimmingMode::Exact, 0)
                .set_deletion_policy(StreamDeletionPolicy::Acked),
        )
        .await?;

    Ok(())
}
