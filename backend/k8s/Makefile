.PHONY: toolbox-up toolbox-down cluster-up cluster-down shell run kubectl rebuild

# Starts the toolbox container in the background (Relative to this Makefile)
toolbox-up:
	docker compose up -d --build

# Stops and removes the toolbox container
toolbox-down:
	docker compose down

HOST_ROOT := $(shell cd ../.. && pwd)

cluster-up:
	@echo "Ensuring the k8s-toolbox container is running..."
	@docker compose up -d
	@echo "Ensuring logs directory exists at project root..."
	@mkdir -p $(HOST_ROOT)/logs
	@echo "Spinning up the cluster and auto-deploying manifests..."
	@docker exec -e HOST_ROOT="$(HOST_ROOT)" -i k8s-toolbox k3d cluster create --config backend/k8s/k3d-config.yaml

cluster-down:
	@echo "Deleting the K3d cluster..."
	@# The '-' at the start of this line tells Make to ignore errors if the toolbox is already gone
	-docker exec k8s-toolbox k3d cluster delete dev-cluster
	@echo "Shutting down the toolbox..."
	@docker compose down

# Destroys everything and rebuilds from scratch
rebuild: cluster-down toolbox-down
	@sleep 2
	$(MAKE) cluster-up

# Opens an interactive terminal inside the toolbox for manual debugging
shell:
	docker exec -it k8s-toolbox bash

# Run arbitrary commands
run:
	@docker exec -it k8s-toolbox $(CMD)

# Run kubectl commands
kubectl:
	@docker exec -it k8s-toolbox kubectl $(CMD)

status:
	@echo "--- CLUSTER STATUS (WIDE) ---"
	@docker exec -it k8s-toolbox kubectl get pods -A -o wide

# Checks the health of the nodes
nodes:
	@echo "--- NODE HEALTH ---"
	@docker exec -it k8s-toolbox kubectl get nodes -o wide

# Describes a specific app in the backend namespace (Usage: make describe APP=booklib-api)
describe:
	@docker exec -it k8s-toolbox kubectl describe deployment $(APP) -n backend

# Fetches logs for a specific app (Usage: make logs APP=booklib)
logs:
	@docker exec -it k8s-toolbox kubectl logs -l app=$(APP) -n backend --tail=50

# Checks the Traefik Ingress routing rules
routes:
	@echo "--- ACTIVE INGRESS ROUTES ---"
	@docker exec -it k8s-toolbox kubectl get ingress -A

watch:
	@docker exec -it k8s-toolbox kubectl get pods -n backend -w

# Updates the dashboard instantly without rebuilding the cluster
dash:
	@echo "Updating Dashboard..."
	@cat manifests/dashboard.json | docker exec -i k8s-toolbox kubectl delete configmap fastapi-developer-dashboard -n monitoring --ignore-not-found
	@cat manifests/dashboard.json | docker exec -i k8s-toolbox kubectl create configmap fastapi-developer-dashboard \
		--namespace monitoring \
		--from-file=fastapi-logs.json=/dev/stdin \
		--dry-run=client -o yaml | docker exec -i k8s-toolbox kubectl apply -f -
	@docker exec -i k8s-toolbox kubectl label cm fastapi-developer-dashboard grafana_dashboard=1 -n monitoring --overwrite

logs-up:
	@echo "Ensuring the k8s-toolbox container is running..."
	@docker compose up -d
	@echo "Ensuring logs directory exists at project root..."
	@mkdir -p $(HOST_ROOT)/logs
	@echo "Spinning up the cluster with ONLY Logging infrastructure..."
	@docker exec -e HOST_ROOT="$(HOST_ROOT)" -i k8s-toolbox k3d cluster create --config backend/k8s/k3d-logs-only.yaml
	@echo ""
	@echo "=========================================================="
	@echo "✅ LOGGING ENVIRONMENT READY"
	@echo "📊 Grafana URL: http://grafana.localhost:8080"
	@echo "👤 Username:    admin"
	@echo "🔑 Password:    Rust!"
	@echo "=========================================================="

logs-rebuild: cluster-down logs-up

