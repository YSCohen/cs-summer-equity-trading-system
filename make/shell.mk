.PHONY: shell run kubectl shell-api shell-ui shell-postgres shell-pooler

# ==========================================
# 🔍 INTERACTIVE SHELLS
# ==========================================

shell: ## Opens an interactive Shell
	$(DOCKER) exec -it k8s-toolbox bash

run: ## Runs anything in CMD=""
	@$(DOCKER) exec -it k8s-toolbox $(CMD)

kubectl: ## Runs kubectl CMD=""
	@$(DOCKER) exec -it k8s-toolbox kubectl $(CMD)

shell-api: ## 🔌 Connecting to FastAPI backend...
	@echo "🔌 Connecting to FastAPI backend..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec -it deployment/fastapi-api -n backend -- /bin/sh

shell-ui: ## 🔌 Connecting to Streamlit frontend...
	@echo "🔌 Connecting to Streamlit frontend..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec -it deployment/streamlit -n frontend -- /bin/sh

shell-postgres: ## 🔌 Connecting to CNPG primary Postgres container...
	@echo "🔌 Connecting to CNPG primary..."
	@$(DOCKER) exec -it k8s-toolbox bash -c 'POD=$$(kubectl get pods -n data -l "cnpg.io/cluster=trading-db,cnpg.io/instanceRole=primary" -o jsonpath="{.items[0].metadata.name}"); kubectl exec -it $$POD -n data -- /bin/bash'

shell-pooler: ## 🔌 Connecting to PgBouncer pooler container...
	@echo "🔌 Connecting to PgBouncer pooler..."
	@$(DOCKER) exec -it k8s-toolbox bash -c 'POD=$$(kubectl get pods -n data -l "cnpg.io/poolerName=trading-pooler" -o jsonpath="{.items[0].metadata.name}"); kubectl exec -it $$POD -n data -- /bin/bash'
