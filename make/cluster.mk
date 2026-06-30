# ==========================================
# 🏗️ TOOLBOX & CLUSTER LIFECYCLE
# ==========================================

up: cluster-up ## Start up the entire project

down: ## Delete the entire project
	@bash cluster_down.sh

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

cluster-up-yehuda: ## Deploy from Yehuda's personal fork
	@echo "🚀 Deploying from Yehuda's fork..."
	@bash cluster_up.sh --yehuda

cluster-up-will: ## Deploy from Will's personal fork
	@echo "🚀 Deploying from Will's fork..."
	@bash cluster_up.sh --will

cluster-down: ## Delete the local k3d dev cluster
	-$(DOCKER) exec k8s-toolbox k3d cluster delete dev-cluster

rebuild: cluster-down toolbox-down ## Nuke everything and rebuild from scratch
	@sleep 2
	$(MAKE) --no-print-directory cluster-up-sean
