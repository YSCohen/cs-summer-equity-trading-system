#!/usr/bin/env bash

# Exit immediately if a command fails
set -e

# 1. Establish the absolute Project Root (where this script lives)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "🪵  Starting the Equity Trading Logging Environment"
echo "=========================================================="

# 2. Check for Container Engine
ENGINE=""
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    ENGINE="docker"
elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
    ENGINE="podman"
else
    echo "❌ ERROR: Neither Docker nor Podman is running."
    exit 1
fi
echo "✅ Detected container engine: $ENGINE"

# 3. Locate the correct Socket
USER_ID=$(id -u)
ACTUAL_SOCK="/var/run/docker.sock"

if [[ "$ENGINE" == "podman" ]]; then
    if [ -S "/run/user/$USER_ID/podman/podman.sock" ]; then
        ACTUAL_SOCK="/run/user/$USER_ID/podman/podman.sock"
    elif [ -S "/run/podman/podman.sock" ]; then
        ACTUAL_SOCK="/run/podman/podman.sock"
    else
        ACTUAL_SOCK="$HOME/.local/share/containers/podman/machine/podman.sock"
    fi
else
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
        ACTUAL_SOCK="//var/run/docker.sock"
    elif [ ! -S "$ACTUAL_SOCK" ]; then
        if [ -S "/run/user/$USER_ID/docker.sock" ]; then
            ACTUAL_SOCK="/run/user/$USER_ID/docker.sock"
        elif [ -S "$HOME/.docker/run/docker.sock" ]; then
            ACTUAL_SOCK="$HOME/.docker/run/docker.sock"
        fi
    fi
fi
echo "✅ Using socket at: $ACTUAL_SOCK"

# 4. Create log directories reliably at the PROJECT ROOT
echo "✅ Preparing local log directories..."
mkdir -p "$PROJECT_ROOT/logs/FastAPI" "$PROJECT_ROOT/logs/Postgres" "$PROJECT_ROOT/logs/Redis" "$PROJECT_ROOT/logs/Streamlit"
chmod -R 777 "$PROJECT_ROOT/logs/" 2>/dev/null || true

# 5. Navigate securely into the Kubernetes directory
if [ ! -d "$PROJECT_ROOT/backend/k8s" ]; then
    echo "❌ ERROR: Directory 'backend/k8s' not found!"
    exit 1
fi
cd "$PROJECT_ROOT/backend/k8s"

# Write the .env file so Compose can read the socket path
echo "DOCKER_HOST_PATH=$ACTUAL_SOCK" >.env

# 6. Fix File Permissions
echo "✅ Fixing configuration file permissions..."
chmod 755 . 2>/dev/null || true
chmod 644 k3d-*.yaml 2>/dev/null || true
chmod -R 755 manifests 2>/dev/null || true

# 7. Boot Sequence
echo "🧹 Cleaning up previous logging environment..."
set +e # Disable strict mode temporarily for cleanup
$ENGINE exec k8s-toolbox k3d cluster delete dev-cluster 2>/dev/null
# Added -v to completely wipe old volumes/DBs
$ENGINE compose down -v 2>/dev/null
set -e

echo "📦 Starting the k8s-toolbox..."
$ENGINE compose up -d

# Give Docker a moment to attach the volume before firing commands
sleep 2

echo "🚀 Spinning up the cluster with ONLY Logging infrastructure..."
# We pass the absolute PROJECT_ROOT we calculated at the top
$ENGINE exec -e HOST_ROOT="$PROJECT_ROOT" -i k8s-toolbox k3d cluster create --config backend/k8s/k3d-logs-only.yaml

echo ""
echo "=========================================================="
echo "✅ LOGGING ENVIRONMENT READY"
echo "📊 Grafana URL: http://grafana.localhost:8080"
echo "👤 Username:    admin"
echo "🔑 Password:    Rust!"
echo "=========================================================="
