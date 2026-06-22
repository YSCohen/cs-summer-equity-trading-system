#!/usr/bin/env bash

# Highly defensive scripting
set -euo pipefail

# Establish the absolute Project Root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "🛑 Shutting Down the Full Equity Trading Environment"
echo "=========================================================="

# 1. Check for Container Engine
ENGINE=""
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    ENGINE="docker"
elif command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
    ENGINE="podman"
else
    echo "❌ ERROR: Neither Docker nor Podman is running."
    exit 1
fi

echo "🧹 Destroying K3d cluster..."
# Temporarily disable strict exit for the deletion in case it doesn't exist
set +e
$ENGINE exec k8s-toolbox k3d cluster delete dev-cluster >/dev/null 2>&1
set -e

echo "📦 Tearing down k8s-toolbox and volumes..."
cd "$PROJECT_ROOT/backend/k8s"

# The -v flag ensures any attached docker volumes are cleanly wiped
$ENGINE compose down -v

echo "✅ Full trading environment successfully shut down and cleaned!"
