<#
.SYNOPSIS
    Starts the Equity Trading Logging Environment locally.
.DESCRIPTION
    Bootstraps the K3d Kubernetes cluster, Promtail, Loki, and Grafana.
    Must be run from the root of the repository.
#>

# DEFENSE 1: Strict Mode (Exits immediately if a PowerShell command fails)
$ErrorActionPreference = "Stop"

# 1. Establish the absolute Project Root (Works exactly like BASH_SOURCE)
$ProjectRoot = $PSScriptRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🪵  Starting the Equity Trading Logging Environment" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 2. Safely Check for Container Engine
$Engine = ""
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $Engine = "docker"
} elseif (Get-Command podman -ErrorAction SilentlyContinue) {
    $Engine = "podman"
} else {
    Write-Host "❌ ERROR: Neither Docker nor Podman is running or you lack permissions." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Detected container engine: $Engine" -ForegroundColor Green

# 3. Locate the correct Socket (Windows mapping specifically)
$ActualSock = "//var/run/docker.sock"
Write-Host "✅ Using socket at: $ActualSock" -ForegroundColor Green

# 4. Create log directories reliably at the PROJECT ROOT
Write-Host "✅ Preparing local log directories..." -ForegroundColor Green
$LogDirs = @("FastAPI", "Postgres", "Redis", "Streamlit")
foreach ($Dir in $LogDirs) {
    $null = New-Item -ItemType Directory -Force -Path "$ProjectRoot\logs\$Dir"
}

# 5. Navigate securely into the Kubernetes directory
if (-not (Test-Path "$ProjectRoot\backend\k8s")) {
    Write-Host "❌ ERROR: Directory 'backend\k8s' not found!" -ForegroundColor Red
    exit 1
}
Set-Location "$ProjectRoot\backend\k8s"

# Write the .env file so Compose can read the socket path
Set-Content -Path ".env" -Value "DOCKER_HOST_PATH=$ActualSock"

# 6. Boot Sequence (Temporarily disable strict mode so cleanup errors don't crash the script)
Write-Host "🧹 Cleaning up previous logging environment..." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"

# Redirect output and errors to null to silently handle "container not found" errors
& $Engine exec k8s-toolbox k3d cluster delete dev-cluster 2>$null
# DEFENSE 2: Added -v to completely wipe old volumes/DBs just like the bash script
& $Engine compose down -v 2>$null

# Re-enable strict mode
$ErrorActionPreference = "Stop"

Write-Host "📦 Starting the k8s-toolbox..." -ForegroundColor Green
& $Engine compose up -d

# Give Docker a moment to attach the volume before firing commands
Start-Sleep -Seconds 2

Write-Host "🚀 Spinning up the cluster with ONLY Logging infrastructure..." -ForegroundColor Cyan
# DEFENSE 3: We must convert Windows backslashes (C:\foo\bar) to forward slashes (C:/foo/bar)
# so the Linux container doesn't misinterpret the HOST_ROOT path!
$LinuxProjectRoot = $ProjectRoot -replace '\\', '/'

& $Engine exec -e HOST_ROOT="$LinuxProjectRoot" -i k8s-toolbox k3d cluster create --config k3d-logs-only.yaml

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "✅ LOGGING ENVIRONMENT READY" -ForegroundColor Green
Write-Host "📊 Grafana URL: http://grafana.localhost:8080"
Write-Host "👤 Username:    admin"
Write-Host "🔑 Password:    Rust!"
Write-Host "==========================================================" -ForegroundColor Cyan
