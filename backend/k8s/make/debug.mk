## ==========================================
# 🕵️ DOWNWARD API & ENV DEBUGGING
# ==========================================

debug-api-manifest: ## 1. Check if the cluster actually received your new YAML
	@echo "🔍 Inspecting the Deployment manifest directly on the cluster..."
	@$(DOCKER) exec -it k8s-toolbox kubectl get deployment fastapi-api -n backend -o yaml | grep -A 15 "env:"

debug-api-env: ## 2. Check the live environment variables inside the running Pod
	@echo "🔍 Executing 'env' inside the active FastAPI pod..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec deployment/fastapi-api -n backend -- env | grep -E "NODE|POD|Worker|GIT|ENV"

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

shell-worker: ## 🔌 Connecting to Trade-Writer worker...
	@echo "🔌 Connecting to Trade-Writer worker..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec -it deployment/trade-writer -n backend -- /bin/sh

shell-postgres: ## 🔌 Connecting to Postgres container...
	@echo "🔌 Connecting to Postgres container..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec -it statefulset/postgres -n data -- /bin/sh

psql: ## 🐘 Starting interactive PostgreSQL session...
	@echo "🐘 Starting interactive PostgreSQL session..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec -it statefulset/postgres -n data -- psql -U trade_admin -d trading

redis-cli: ## 🔴 Connecting to Redis CLI...
	@echo "🔴 Connecting to Redis CLI..."
	@$(DOCKER) exec -it k8s-toolbox kubectl exec -it deployment/redis -n data -- redis-cli

seed-trades: ## 🌱 Spawning temporary uv pod to inject fake trades...
	@echo "🌱 Spawning temporary uv pod to inject fake trades..."
	@cat backend/DB/redis-postgres-syncers/test/trades.py | \
	$(DOCKER) exec -i k8s-toolbox kubectl run trade-seeder --rm -i -n backend \
		--image=ghcr.io/astral-sh/uv:alpine \
		--env="REDIS_HOST=redis.data.svc.cluster.local" \
		--restart=Never \
		-- sh -c "cat > script.py && uv run script.py"
