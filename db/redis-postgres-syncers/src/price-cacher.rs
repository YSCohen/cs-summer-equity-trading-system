//! pull market prices of S&P 500 from yahoo finance API
//! and cache them in redis for fast access by the API

use dotenvy::dotenv;
use jiff::Timestamp;
use redis::aio::MultiplexedConnection;
use serde::{Deserialize, Serialize};
use std::env;
use std::error::Error;
use tracing::{debug, error, info};
use yahoo_finance_api as yahoo;

#[tokio::main]
async fn main() {
    let _ = dotenv();

    if let Err(err) = helpers::init_tracing("price-cacher") {
        eprintln!("failed to initialize tracing: {:?}", err);
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        std::process::exit(1);
    }

    info!("=== STARTING MARKET PRICE CACHER ===");

    // Run the main pipeline and catch any fatal initialization errors
    if let Err(err) = run().await {
        error!(?err, "Fatal error");
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        std::process::exit(1);
    }
}

async fn run() -> Result<(), Box<dyn std::error::Error>> {
    let _ = dotenv();

    let redis_url = env::var("REDIS_URL").map_err(|_| "REDIS_URL must be set")?;
    let interval: u64 = env::var("DELAY")
        .map_err(|_| "DELAY must be set")?
        .parse()
        .map_err(|_| "DELAY must be an int")?;

    debug!("read env vars");

    // connect to redis
    let redis_client = redis::Client::open(redis_url)?;
    let mut redis_conn = redis_client.get_multiplexed_async_connection().await?;
    debug!("connected to redis");

    loop {
        update_all_cached_prices(&mut redis_conn).await?;
        info!("updated all cached prices");

        tokio::select! {
            () = tokio::time::sleep(std::time::Duration::from_secs(interval)) => {}
            () = helpers::shutdown_signal() => {
                info!("Shutdown signal received. Exiting loop gracefully...");
                return Ok(());
            }
        }
    }
}

async fn update_all_cached_prices(
    redis_conn: &mut MultiplexedConnection,
) -> Result<(), Box<dyn Error>> {
    let mut pipe = redis::pipe();

    let sp500_symbols = fetch_sp500_symbols().await?;

    for symbol in sp500_symbols {
        let quote = get_quote_json(&symbol).await?;
        pipe.hset("market_prices", &symbol, &quote);
    }
    debug!("wrote quotes for all symbols to pipe...");

    pipe.query_async::<()>(redis_conn).await?;
    debug!("executed pipe");

    Ok(())
}

#[derive(Serialize)]
struct MarketData {
    open_price: f64,
    latest_price: f64,
    latest_time: String,
}

async fn get_quote_json(symbol: &str) -> Result<String, Box<dyn Error>> {
    let provider = yahoo::YahooConnector::new()?;

    // 1-minute intervals for the current day
    let response = provider.get_quote_range(symbol, "1m", "1d").await?;
    let quotes = response.quotes()?;

    // first in day is open, last is latest available
    let first_quote = quotes.first().ok_or("No opening price data found")?;
    let last_quote = quotes.last().ok_or("No current price data found")?;

    let data = MarketData {
        open_price: first_quote.open,
        latest_price: last_quote.close,
        // ts will be string formatted in ISO 8601 - YYYY-MM-DDTHH:MM:SSZ
        latest_time: Timestamp::from_second(last_quote.timestamp as i64)?.to_string(),
    };

    // Ok(serde_json::to_string_pretty(&data)?)
    Ok(serde_json::to_string(&data)?)
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
