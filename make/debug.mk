## ==========================================
# 🕵️ DOWNWARD API & ENV DEBUGGING
# ==========================================

bounce-api: ## 3. Force a graceful restart of the FastAPI pods to pick up new Env Vars
	@echo "🔄 Forcing a rolling restart of the FastAPI deployment..."
	@$(DOCKER) exec -it k8s-toolbox kubectl rollout restart deployment/fastapi-api -n backend

# ==========================================
# 🔍 INTERACTIVE SHELLS & DATABASES
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

shell-postgres: ## 🔌 Connecting to Postgres container...
	@echo "🔌 Connecting to Postgres container..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec -it statefulset/postgres -n data -- /bin/sh

psql: ## 🐘 Starting interactive PostgreSQL session...
	@echo "🐘 Starting interactive PostgreSQL session..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec -it statefulset/postgres -n data -- psql -U trade_admin -d trading

redis-cli: ## 🔴 Connecting to Redis CLI dynamically...
	@echo "🔴 Finding active Redis node and launching CLI..."
	@$(DOCKER) exec -it k8s-toolbox bash -c 'POD=$$(kubectl get pods -n data -l "app.kubernetes.io/name=redis" -o jsonpath="{.items[0].metadata.name}" 2>/dev/null || kubectl get pods -n data -l "app=redis" -o jsonpath="{.items[0].metadata.name}"); kubectl exec -it $$POD -n data -- redis-cli'

redis-sentinel: ## 🛡️ Connecting to Redis Sentinel CLI...
	@echo "🛡️ Connecting to Sentinel to check quorum..."
	@$(DOCKER) exec -it k8s-toolbox bash -c 'POD=$$(kubectl get pods -n data -l "app.kubernetes.io/name=redis,app.kubernetes.io/component=sentinel" -o jsonpath="{.items[0].metadata.name}"); kubectl exec -it $$POD -n data -- redis-cli -p 26379 info sentinel'
