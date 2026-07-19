#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "🔄 Reloading Locust configuration..."
echo "=========================================================="

# ============================================================
# Detect container engine
# ============================================================
ENGINE=""
if command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
    ENGINE="podman"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    ENGINE="docker"
else
    echo "❌ ERROR: Neither Docker nor Podman is running."
    exit 1
fi
echo "✅ Container engine: $ENGINE"

# 2. Recreate the ConfigMap by piping the local Python file into the toolbox
echo "📦 Updating ConfigMap 'locust-config'..."
$ENGINE exec -i k8s-toolbox sh -c 'kubectl create configmap locust-config -n load-testing --from-file=locustfile.py=/dev/stdin -o yaml --dry-run=client | kubectl apply -f -' \
    <"$PROJECT_ROOT/locust/locustfile.py"

# 3. Force the Locust deployment to restart and pick up the new configuration
echo "♻️ Restarting Locust pods to apply changes..."
$ENGINE exec -i k8s-toolbox kubectl rollout restart deployment/locust-load-tester -n load-testing

echo "✅ Restart triggered — pods will pick up the new configuration shortly."
