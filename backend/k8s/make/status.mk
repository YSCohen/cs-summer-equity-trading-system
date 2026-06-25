# ==========================================
# 📊 CLUSTER STATUS
# ==========================================

status: ## 🟢 CURRENT POD STATUS:
	@echo "🟢 CURRENT POD STATUS:"
	@$(DOCKER) exec -it k8s-toolbox kubectl get pods -A

status-wide: ## 🌐 WIDE POD OVERVIEW:
	@echo "🌐 WIDE POD OVERVIEW:"
	@$(DOCKER) exec -it k8s-toolbox kubectl get pods -A -o wide

status-svc: ## 🔌 ACTIVE NETWORK SERVICES:
	@echo "🔌 ACTIVE NETWORK SERVICES:"
	@$(DOCKER) exec -it k8s-toolbox kubectl get svc -A

sync:
	$(DOCKER) exec -it k8s-toolbox flux reconcile kustomization dev-stack --with-source

adminer-info: ## 🌐 Adminer UI: http://adminer.localhost:8080
	@echo "🌐 Adminer UI: http://adminer.localhost:8080"
	@echo "🔍 Fetching Postgres Credentials from cluster..."
	@echo -n "User: "
	@$(DOCKER) exec -it k8s-toolbox kubectl get secret db-credentials -n data -o jsonpath='{.data.POSTGRES_USER}' | base64 -d; echo ""
	@echo -n "Pass: "
	@$(DOCKER) exec -it k8s-toolbox kubectl get secret db-credentials -n data -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d; echo ""
