.PHONY: toolbox-up toolbox-down cluster-up cluster-down shell run kubectl rebuild logs-up logs-rebuild grafana-pass

# Allow overriding the container engine (defaults to docker)
DOCKER ?= docker
HOST_ROOT := $(shell cd ../.. && pwd)

# Starts the toolbox container in the background
toolbox-up:
	$(DOCKER) compose up -d --build

# Stops and removes the toolbox container
toolbox-down:
	$(DOCKER) compose down

# Uses the toolbox to create the K3s cluster. Manifests are auto-injected via config!
cluster-up: toolbox-up
	@echo "Spinning up the cluster and auto-deploying manifests..."
	$(DOCKER) exec k8s-toolbox k3d cluster create --config backend/k8s/k3d-config.yaml
	@echo "Cluster is ready and resources are deploying!"

# Uses the toolbox to delete the cluster
cluster-down:
	-$(DOCKER) exec k8s-toolbox k3d cluster delete dev-cluster

# The ultimate IaC command: Destroy everything and rebuild from scratch
rebuild: cluster-down toolbox-down
	@sleep 2
	$(MAKE) cluster-up

# Logs-only targets
logs-up:
	@echo "Ensuring the k8s-toolbox container is running..."
	$(DOCKER) compose up -d
	@echo "Ensuring logs directory exists at project root..."
	@mkdir -p $(HOST_ROOT)/logs
	@echo "Spinning up the cluster with ONLY Logging infrastructure..."
	$(DOCKER) exec -e HOST_ROOT="$(HOST_ROOT)" -i k8s-toolbox k3d cluster create --config backend/k8s/k3d-logs-only.yaml
	@echo ""
	@echo "=========================================================="
	@echo "✅ LOGGING ENVIRONMENT READY"
	@echo "📊 Grafana URL: http://grafana.localhost:8080"
	@echo "👤 Username:    admin"
	@echo "🔑 Password:    Rust!"
	@echo "=========================================================="

logs-rebuild: cluster-down toolbox-down logs-up

# Opens an interactive terminal inside the toolbox for manual debugging
shell:
	$(DOCKER) exec -it k8s-toolbox bash

# Run arbitrary commands via: make run CMD="k3d cluster list"
run:
	@$(DOCKER) exec -it k8s-toolbox $(CMD)

# Run kubectl commands via: make kubectl CMD="get pods -A"
kubectl:
	@$(DOCKER) exec -it k8s-toolbox kubectl $(CMD)

# The "Apply" command to manually refresh manifests if you don't want to rebuild
apply:
	@tar -cf - manifests/ | $(DOCKER) exec -i k8s-toolbox sh -c "tar -xf - && kubectl apply -f manifests/"

sync-dashboard:
	@$(DOCKER) exec -i k8s-toolbox sh -c "kubectl create configmap fastapi-developer-dashboard --from-file=dashboard.json=./manifests/dashboard.json -n monitoring --dry-run=client -o yaml | kubectl apply -f -"
	@$(DOCKER) exec -i k8s-toolbox kubectl label configmap fastapi-developer-dashboard -n monitoring grafana_dashboard=1 --overwrite
	@echo "Dashboard synced! Refresh Grafana in your browser."
