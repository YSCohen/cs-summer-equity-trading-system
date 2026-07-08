//! store historical market data of s&p 500 stocks' prices in redis as time series
//!
//! Each symbol gets a 1-minute series that feeds three coarser tiers through
//! compaction rules. Every tier carries its own retention, so history
//! automatically decays into progressively coarser buckets as it ages:
//!
//!   price:{SYM}       raw 1m samples, kept 1 hour
//!   price:{SYM}:1h    hourly bars,    kept 1 day
//!   price:{SYM}:1d    daily bars,     kept 1 month
//!   price:{SYM}:1w    weekly bars,    kept 1 year
//!
//! The API can read a window at the appropriate resolution with TS.RANGE, e.g.
//! `TS.RANGE price:AAPL:1d - +` for the last month of daily closes.

use dotenvy::dotenv;
use redis::aio::MultiplexedConnection;
use serde::Deserialize;
use std::error::Error;
use tracing::{debug, error, info, warn};
use yahoo_finance_api as yahoo;

/// Retention of the raw 1-minute source series (1 hour, in milliseconds).
const RAW_RETENTION_MS: i64 = 60 * 60 * 1000;

/// A compacted tier derived from the raw series: how wide each bucket is and
/// how long the downsampled bars are kept before they expire.
struct Tier {
    suffix: &'static str,
    bucket_ms: i64,
    retention_ms: i64,
}

const TIERS: &[Tier] = &[
    // hourly bars, kept for a day
    Tier {
        suffix: "1h",
        bucket_ms: 60 * 60 * 1000,
        retention_ms: 24 * 60 * 60 * 1000,
    },
    // daily bars, kept for a month
    Tier {
        suffix: "1d",
        bucket_ms: 24 * 60 * 60 * 1000,
        retention_ms: 30 * 24 * 60 * 60 * 1000,
    },
    // weekly bars, kept for the rest of the year
    Tier {
        suffix: "1w",
        bucket_ms: 7 * 24 * 60 * 60 * 1000,
        retention_ms: 365 * 24 * 60 * 60 * 1000,
    },
];

#[tokio::main]
async fn main() {
    let _ = dotenv();

    if let Err(err) = helpers::init_tracing("price-history-timeseries") {
        eprintln!("failed to initialize tracing: {:?}", err);
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        std::process::exit(1);
    }

    if let Err(err) = run().await {
        error!(?err, "Fatal error");
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        std::process::exit(1);
    }
}

async fn run() -> Result<(), Box<dyn std::error::Error>> {
    let redis_url = helpers::require_env("REDIS_URL")?;
    let interval: u64 = helpers::require_env("DELAY")?
        .parse()
        .map_err(|_| "DELAY must be an int")?;

    debug!("read env vars");

    let mut redis_conn = helpers::connect_redis(redis_url).await;

    let symbols = fetch_sp500_symbols().await?;

    // Provision the raw series + compaction rules once. This is idempotent:
    // already-provisioned symbols are skipped.
    info!(
        "ensuring time series and compaction rules for {} symbols",
        symbols.len()
    );
    for symbol in &symbols {
        ensure_series(&mut redis_conn, symbol).await?;
    }
    debug!("ensured all time series");

    loop {
        append_all_latest_samples(&mut redis_conn, &symbols).await?;
        info!("appended latest samples for all symbols");

        tokio::select! {
            () = tokio::time::sleep(std::time::Duration::from_secs(interval)) => {}
            () = helpers::shutdown_signal() => {
                info!("Shutdown signal received. Exiting loop gracefully...");
                return Ok(());
            }
        }
    }
}

/// Key of the raw 1-minute source series for a symbol.
fn raw_key(symbol: &str) -> String {
    format!("price:{symbol}")
}

/// Create the raw source series and its compaction tiers for a symbol.
///
/// Skips symbols whose raw series already exists so restarts stay cheap, and
/// tolerates "already exists" errors in case provisioning was interrupted.
async fn ensure_series(
    redis_conn: &mut MultiplexedConnection,
    symbol: &str,
) -> Result<(), Box<dyn Error>> {
    let raw = raw_key(symbol);

    let exists: bool = redis::cmd("EXISTS")
        .arg(&raw)
        .query_async(redis_conn)
        .await?;
    if exists {
        return Ok(());
    }

    // raw 1-minute source that everything else is compacted from
    create_series(redis_conn, &raw, RAW_RETENTION_MS, symbol, "1m").await?;

    for tier in TIERS {
        let dest = format!("{raw}:{}", tier.suffix);
        create_series(redis_conn, &dest, tier.retention_ms, symbol, tier.suffix).await?;
        create_rule(redis_conn, &raw, &dest, tier.bucket_ms).await?;
    }

    Ok(())
}

async fn create_series(
    redis_conn: &mut MultiplexedConnection,
    key: &str,
    retention_ms: i64,
    symbol: &str,
    tier: &str,
) -> Result<(), Box<dyn Error>> {
    let mut cmd = redis::cmd("TS.CREATE");
    cmd.arg(key)
        .arg("RETENTION")
        .arg(retention_ms)
        .arg("DUPLICATE_POLICY")
        .arg("LAST")
        .arg("LABELS")
        .arg("symbol")
        .arg(symbol)
        .arg("tier")
        .arg(tier);

    run_ignoring_exists(redis_conn, &cmd).await
}

async fn create_rule(
    redis_conn: &mut MultiplexedConnection,
    source: &str,
    dest: &str,
    bucket_ms: i64,
) -> Result<(), Box<dyn Error>> {
    // "last" downsamples each bucket to its closing price, matching how a
    // coarser candlestick's close is defined.
    let mut cmd = redis::cmd("TS.CREATERULE");
    cmd.arg(source)
        .arg(dest)
        .arg("AGGREGATION")
        .arg("last")
        .arg(bucket_ms);

    run_ignoring_exists(redis_conn, &cmd).await
}

/// Run a command, swallowing the benign errors RedisTimeSeries returns when a
/// series or rule was already created by a previous run.
async fn run_ignoring_exists(
    redis_conn: &mut MultiplexedConnection,
    cmd: &redis::Cmd,
) -> Result<(), Box<dyn Error>> {
    match cmd.query_async::<()>(redis_conn).await {
        Ok(()) => Ok(()),
        Err(e) => {
            let msg = e.to_string().to_lowercase();
            if msg.contains("already exists") || msg.contains("already has") {
                Ok(())
            } else {
                Err(e.into())
            }
        }
    }
}

/// Fetch the latest price for every symbol and append it to the raw series in a
/// single pipeline. The compaction rules fan each sample out to the tiers.
async fn append_all_latest_samples(
    redis_conn: &mut MultiplexedConnection,
    symbols: &[String],
) -> Result<(), Box<dyn Error>> {
    let mut pipe = redis::pipe();

    for symbol in symbols {
        let (timestamp_ms, price) = match get_latest_sample(symbol).await {
            Ok(sample) => sample,
            Err(err) => {
                warn!(symbol, ?err, "skipping symbol with no usable price");
                continue;
            }
        };

        pipe.cmd("TS.ADD")
            .arg(raw_key(symbol))
            .arg(timestamp_ms)
            .arg(price)
            .arg("ON_DUPLICATE")
            .arg("LAST");
    }
    debug!("wrote latest samples for all symbols to pipe...");

    pipe.query_async::<()>(redis_conn).await?;
    debug!("executed pipe");

    Ok(())
}

/// Latest `(timestamp_ms, price)` for a symbol from yahoo's 1-minute intraday
/// feed. Walks back from the most recent bar to skip trailing empty candles,
/// whose close yahoo reports as NaN.
async fn get_latest_sample(symbol: &str) -> Result<(i64, f64), Box<dyn Error>> {
    let provider = yahoo::YahooConnector::new()?;

    let response = provider.get_quote_range(symbol, "1m", "1d").await?;
    let quotes = response.quotes()?;

    let quote = quotes
        .iter()
        .rev()
        .find(|quote| quote.close.is_finite())
        .ok_or("no finite price data found")?;

    // yahoo reports seconds; RedisTimeSeries works in milliseconds
    let timestamp_ms = (quote.timestamp as i64) * 1000;

    Ok((timestamp_ms, quote.close))
}

#[derive(Debug, Deserialize)]
struct Record {
    #[serde(rename = "Symbol")]
    symbol: String,
}

async fn fetch_sp500_symbols() -> Result<Vec<String>, Box<dyn Error>> {
    let response = reqwest::get("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv").await?.text().await?;
    debug!("fetched S&P 500 csv");

    let mut rdr = csv::Reader::from_reader(response.as_bytes());
    let mut symbols = Vec::new();

    for result in rdr.deserialize() {
        let record: Record = result?;
        // Fix for symbols that Yahoo represents differently (e.g., BRK.B instead of BRK-B)
        let formatted_symbol = record.symbol.replace('.', "-");
        symbols.push(formatted_symbol);
    }
    debug!("parsed S&P 500 csv into symbol Vec");

    Ok(symbols)
}
