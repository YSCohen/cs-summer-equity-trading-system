.PHONY: toolbox-up toolbox-down cluster-up cluster-down shell run kubectl rebuild

# Starts the toolbox container in the background (Relative to this Makefile)
toolbox-up:
	docker compose up -d --build

# Stops and removes the toolbox container
toolbox-down:
	docker compose down

# Uses the toolbox to create the K3s cluster. (Uses absolute paths inside the container)
cluster-up: toolbox-up
	@echo "Spinning up the cluster and auto-deploying manifests..."
	docker exec k8s-toolbox k3d cluster create --config backend/k8s/k3d-config.yaml
	@echo "Cluster is ready and resources are deploying!"

# Uses the toolbox to delete the cluster
cluster-down:
	docker exec k8s-toolbox k3d cluster delete dev-cluster

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

# Fetches the auto-generated Grafana admin password
grafana-pass:
	@echo "Grafana Username: admin"
	@echo -n "Grafana Password: "
	@docker exec -it k8s-toolbox kubectl get secret --namespace monitoring loki-stack-grafana -o jsonpath="{.data.admin-password}" | base64 --decode
	@echo ""

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
