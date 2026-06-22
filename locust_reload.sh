#!/usr/bin/env bash

# Highly defensive scripting
set -euo pipefail

# 1. Establish the absolute Project Root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "🔄 Reloading Locust configuration..."
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

# 3. Reload Logic
echo "📦 Updating ConfigMap 'locust-config'..."

# We use dry-run/apply to replace the CM in-place without manual deletion
$ENGINE exec -i k8s-toolbox kubectl create configmap locust-config \
    --from-file=locustfile.py="$PROJECT_ROOT/backend/Locust/locustfile.py" \
    -n load-testing \
    --dry-run=client -o yaml | $ENGINE exec -i k8s-toolbox kubectl apply -f -

echo "🚀 Rolling out new Locust deployment..."
$ENGINE exec -i k8s-toolbox kubectl rollout restart deployment locust-load-tester -n load-testing

echo "✅ Locust reload complete. Waiting for pods..."
$ENGINE exec -i k8s-toolbox kubectl rollout status deployment locust-load-tester -n load-testing

echo ""
echo "=========================================================="
echo "✅ LOCUST RELOADED SUCCESSFULLY"
echo "🌐 URL: http://locust.localhost:8080"
echo "=========================================================="
