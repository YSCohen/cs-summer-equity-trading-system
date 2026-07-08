//! expose build time and commit hash as env vars for helpers::build_info()

use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

fn main() {
    let hash = run_git(&["rev-parse", "--short", "HEAD"]).unwrap_or_else(|| "unknown".into());
    let dirty = match run_git(&["status", "--porcelain"]) {
        Some(s) if !s.is_empty() => "-dirty",
        _ => "",
    };
    println!("cargo:rustc-env=BUILD_GIT_HASH={hash}{dirty}");

    // UTC build time as unix seconds; formatted at log time to avoid jiff dep here
    let build_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    println!("cargo:rustc-env=BUILD_UNIX_SECS={build_unix}");

    // Rebuild when HEAD moves so the hash stays current.
    println!("cargo:rerun-if-changed=.git/HEAD");
    println!("cargo:rerun-if-changed=.git/index");
}

fn run_git(args: &[&str]) -> Option<String> {
    let out = Command::new("git").args(args).output().ok()?;
    if !out.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&out.stdout).trim().to_string())
}
