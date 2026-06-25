# ==========================================
# 🌪️ CHAOS ENGINEERING
# ==========================================

chaos-grafana: ## 🔫 Terminating Grafana UI...
	@echo "🔫 Terminating Grafana UI..."
	@$(DOCKER) exec -it k8s-toolbox kubectl delete pod -l app.kubernetes.io/name=grafana -n monitoring

chaos-api: ## 🔫 Terminating all FastAPI pods...
	@echo "🔫 Terminating all FastAPI pods..."
	@$(DOCKER) exec -it k8s-toolbox kubectl delete pods -l app=fastapi -n backend

chaos-streamlit: ## 🔫 Terminating all Streamlit pods...
	@echo "🔫 Terminating all Streamlit pods..."
	@$(DOCKER) exec -it k8s-toolbox kubectl delete pods -l app=streamlit -n frontend

chaos-worker: ## 🔫 Terminating Trade-Writer worker pods...
	@echo "🔫 Terminating Trade-Writer worker pods..."
	@$(DOCKER) exec -it k8s-toolbox kubectl delete pods -l app=trade-writer -n backend

chaos-redis: ## 🧨 Terminating Redis Pod...
	@echo "🧨 Terminating Redis Pod..."
	@$(DOCKER) exec -it k8s-toolbox kubectl delete pods -l app=redis -n data

chaos-adminer: ## 🧨 Terminating Adminer Pod...
	@echo "🧨 Terminating Adminer Pod..."
	@$(DOCKER) exec -it k8s-toolbox kubectl delete pods -l app=adminer -n data

chaos-node-stop: ## 🔥 Stopping the primary K3s node (Simulating Server Crash)...
	@echo "🔥 Stopping the primary K3s node (Simulating Server Crash)..."
	@$(DOCKER) exec -it k8s-toolbox k3d node stop k3d-dev-cluster-server-0

chaos-node-start: ## 🚑 Rebooting the primary K3s node...
	@echo "🚑 Rebooting the primary K3s node..."
	@$(DOCKER) exec -it k8s-toolbox k3d node start k3d-dev-cluster-server-0
