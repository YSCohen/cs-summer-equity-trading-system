.PHONY: toolbox-up toolbox-down cluster-up cluster-down shell run kubectl rebuild logs-up logs-rebuild grafana-pass apply sync-dashboard test test-stop status status-wide status-svc

# Allow overriding the container engine (defaults to docker)
DOCKER ?= docker
HOST_ROOT := $(shell cd ../.. && pwd)
export HOST_ROOT

# Starts the toolbox container in the background
toolbox-up:
	$(DOCKER) compose up -d --build

# Stops and removes the toolbox container
toolbox-down:
	$(DOCKER) compose down

# Uses the toolbox to create the K3s cluster. Manifests are auto-injected via config!
cluster-up: toolbox-up
	@echo "Spinning up the cluster and auto-deploying manifests..."
	$(DOCKER) exec -e HOST_ROOT="$(HOST_ROOT)" -i k8s-toolbox k3d cluster create --config backend/k8s/k3d-config.yaml
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

# Run this via: make test
test:
	@echo "Awakening Locust from Scale-to-Zero..."
	@$(DOCKER) exec -i k8s-toolbox kubectl scale deployment locust-load-tester --replicas=1
	@echo "Waiting for pod to be ready (this may take up to 60 seconds)..."
	@$(DOCKER) exec -i k8s-toolbox kubectl wait --for=condition=available --timeout=60s deployment/locust-load-tester || \
		(echo "❌ TIMEOUT! Fetching crash logs..." && \
		$(DOCKER) exec -i k8s-toolbox kubectl get pods -l app=locust && \
		echo "--- POD LOGS ---" && \
		$(DOCKER) exec -i k8s-toolbox kubectl logs -l app=locust && exit 1)
	@echo "✅ Locust is running!"
	@echo "🌐 Open your browser to http://locust.localhost:8080"

test-stop:
	@echo "Putting Locust back to sleep..."
	@$(DOCKER) exec -i k8s-toolbox kubectl scale deployment locust-load-tester --replicas=0

# ==========================================
# 📊 CLUSTER STATUS DASHBOARDS
# ==========================================

# Get a quick overview of all running pods
status:
	@echo "🟢 CURRENT POD STATUS:"
	@$(DOCKER) exec -it k8s-toolbox kubectl get pods -A

# Get a detailed, wide view of all pods (IPs, Nodes, Readiness)
status-wide:
	@echo "🌐 WIDE POD OVERVIEW:"
	@$(DOCKER) exec -it k8s-toolbox kubectl get pods -A -o wide

# See all active network services and their exposed ports
status-svc:
	@echo "🔌 ACTIVE NETWORK SERVICES:"
	@$(DOCKER) exec -it k8s-toolbox kubectl get svc -A

sync: 
	docker exec -it k8s-toolbox flux reconcile kustomization dev-stack --with-source

reload-grafana:
	@$(DOCKER) exec -it k8s-toolbox kubectl delete pod -l app.kubernetes.io/name=grafana -n monitoring
