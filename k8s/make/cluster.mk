# ==========================================
# 🏗️ TOOLBOX & CLUSTER LIFECYCLE
# ==========================================

toolbox-up: ## Start the containerized k8s-toolbox
	@cd k8s && $(DOCKER) compose up -d --build

toolbox-down: ## Tear down the k8s-toolbox
	@cd k8s && $(DOCKER) compose down

cluster-up: ## Deploy from UPSTREAM (production-like)
	@echo "🚀 Deploying from UPSTREAM (production-like)..."
	@bash cluster_up.sh

cluster-up-sean: ## Deploy from Sean's personal fork
	@echo "🚀 Deploying from Sean's fork..."
	@bash cluster_up.sh --sean

cluster-up-max: ## Deploy from Max's personal fork
	@echo "🚀 Deploying from Max's fork..."
	@bash cluster_up.sh --max

cluster-down: ## Delete the local k3d dev cluster
	-$(DOCKER) exec k8s-toolbox k3d cluster delete dev-cluster

rebuild: cluster-down toolbox-down ## Nuke everything and rebuild from scratch
	@sleep 2
	$(MAKE) --no-print-directory cluster-up-sean
