#!/usr/bin/env bash

# Exit immediately if a command fails
set -e

# Establish the absolute Project Root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "🛑  Shutting Down the Equity Trading Logging Environment"
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
# We use '|| true' so the script doesn't crash if the cluster is already deleted
$ENGINE exec k8s-toolbox k3d cluster delete dev-cluster 2>/dev/null || true

echo "📦 Tearing down k8s-toolbox..."
cd "$PROJECT_ROOT/backend/k8s"
# The -v flag removes the attached volumes
$ENGINE compose down -v

echo "✅ Logging environment successfully shut down!"
