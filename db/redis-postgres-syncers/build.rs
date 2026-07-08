//! Expose build metadata env vars (source, commit, time) as build-time env vars
//! for `helpers::build_info()`.

use std::time::{SystemTime, UNIX_EPOCH};

fn main() {
    // builder and commit hash are just passed along from build env
    let source = std::env::var("BUILD_SOURCE").unwrap_or("<mysterious builder>".to_string());
    println!("cargo:rustc-env=BUILD_SOURCE={source}");

    let hash = std::env::var("BUILD_GIT_HASH").unwrap_or("<unknown commit>".to_string());
    println!("cargo:rustc-env=BUILD_GIT_HASH={hash}");

    // UTC build time as unix seconds; formatted at log time to avoid a date dep here.
    let build_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    println!("cargo:rustc-env=BUILD_UNIX_SECS={build_unix}");
}
