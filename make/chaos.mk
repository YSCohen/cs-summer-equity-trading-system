# ==========================================
# 🌪️ CHAOS ENGINEERING (SCALE & KILL)
# ==========================================

SCALE_APPS_BANK = fastapi streamlit locust adminer db-syncer trade-writer price-cacher
SCALE_DATA_BANK = redis postgres pgbouncer
KILL_BANK = fastapi streamlit locust adminer db-syncer trade-writer price-cacher redis grafana

# ------------------------------------------
# 💀 KILL (Simulate Pod Crash)
# ------------------------------------------
chaos-kill: ## 💀 Interactive menu to delete pods for a specific app
	@echo "============================================="
	@echo "    💥 EQUITY TRADING APP - KILL SIMULATOR"
	@echo "============================================="
	@PS3="Select an app to kill (1-9, or type '10' to exit): "; \
	select app in $(KILL_BANK) "Exit"; do \
		if [ "$$app" = "Exit" ]; then echo "Gracefully exiting kill menu."; break; fi; \
		if [ -n "$$app" ]; then \
			ns=$$(case $$app in \
				grafana) echo "monitoring";; \
				locust) echo "load-testing";; \
				streamlit) echo "frontend";; \
				adminer|redis|postgres|pgbouncer) echo "data";; \
				*) echo "backend";; \
			esac); \
			label=$$(case $$app in \
				grafana) echo "app.kubernetes.io/name=grafana";; \
				*) echo "app=$$app";; \
			esac); \
			echo "💀 Killing pods for $$app (Label: $$label) in namespace $$ns..."; \
			$(DOCKER) exec -it k8s-toolbox kubectl delete pods -l "$$label" -n "$$ns"; \
			break; \
		fi; \
	done

# ------------------------------------------
# 📉 SCALE DOWN (Simulate Outage)
# ------------------------------------------
chaos: ## 💥 Interactive menu to scale components down to 0
	@echo "============================================="
	@echo "    💥 EQUITY TRADING APP - CHAOS SCALE DOWN"
	@echo "============================================="
	@echo "Remember: This will suspend Flux! Use 'make restore-all' to resume."
	@PS3="Select a layer to disrupt (1-3, or type '3' to gracefully exit): " ;\
	select layer in "Application Layer (KEDA/Deployments)" "Data Layer (StatefulSets)" "Exit"; do \
		case $$layer in \
			"Application Layer (KEDA/Deployments)") \
				PS3="Select an app to scale down (1-8, or type '8' to go back): "; \
				select app in $(SCALE_APPS_BANK) "Back"; do \
					if [ "$$app" = "Back" ]; then break; fi; \
					if [ -n "$$app" ]; then \
						deploy_name=$$app; ns="backend"; scale_name=""; \
						if [ "$$app" = "locust" ]; then deploy_name="locust-load-tester"; ns="load-testing"; fi; \
						if [ "$$app" = "streamlit" ]; then ns="frontend"; fi; \
						if [ "$$app" = "adminer" ]; then ns="data"; fi; \
						if [ "$$app" = "fastapi" ]; then deploy_name="fastapi-api"; scale_name="fastapi-scaler"; fi; \
						if [ "$$app" = "trade-writer" ]; then scale_name="trade-writer-scaler"; fi; \
						echo "⏸️  Suspending Flux 3-apps kustomization..."; \
						$(DOCKER) exec -it k8s-toolbox flux suspend kustomization 3-apps; \
						echo "🔫 Scaling $$app down to 0 in namespace $$ns..."; \
						if [ "$$app" = "fastapi" ] || [ "$$app" = "trade-writer" ]; then \
							$(DOCKER) exec -it k8s-toolbox kubectl annotate scaledobject $$scale_name -n $$ns autoscaling.keda.sh/paused-replicas="0" --overwrite; \
						else \
							$(DOCKER) exec -it k8s-toolbox kubectl scale deployment $$deploy_name -n $$ns --replicas=0; \
						fi; \
						echo "=========================================================="; \
						echo "⚠️  WARNING: Flux is SUSPENDED. The cluster is in CHAOS mode."; \
						echo "👉  Run 'make restore-all' to resume Flux and recover."; \
						echo "=========================================================="; \
						break 2; \
					fi; \
				done ;; \
			"Data Layer (StatefulSets)") \
				PS3="Select a component to scale down (1-4, or type '4' to go back): "; \
				select data_app in $(SCALE_DATA_BANK) "Back"; do \
					if [ "$$data_app" = "Back" ]; then break; fi; \
					if [ -n "$$data_app" ]; then \
						echo "⏸️  Suspending Flux 2-data kustomization..."; \
						$(DOCKER) exec -it k8s-toolbox flux suspend kustomization 2-data; \
						echo "🔫 Scaling $$data_app down to 0 in namespace data..."; \
						if [ "$$data_app" = "pgbouncer" ]; then \
							$(DOCKER) exec -it k8s-toolbox kubectl scale deployment $$data_app -n data --replicas=0; \
						elif [ "$$data_app" = "redis" ]; then \
							REDIS_STS=$$($(DOCKER) exec -it k8s-toolbox kubectl get sts -n data -l 'app.kubernetes.io/name=redis' -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "redis"); \
							$(DOCKER) exec -it k8s-toolbox kubectl scale statefulset $$REDIS_STS -n data --replicas=0; \
						else \
							$(DOCKER) exec -it k8s-toolbox kubectl scale statefulset $$data_app -n data --replicas=0; \
						fi; \
						echo "=========================================================="; \
						echo "⚠️  WARNING: Flux is SUSPENDED. The cluster is in CHAOS mode."; \
						echo "👉  Run 'make restore-all' to resume Flux and recover."; \
						echo "=========================================================="; \
						break 2; \
					fi; \
				done ;; \
			"Exit") echo "Gracefully exiting chaos menu."; break ;; \
		esac; \
	done

# ------------------------------------------
# 🚑 RESTORE & NODE CONTROL
# ------------------------------------------
restore-all: ## 🚑 Resume Flux to naturally restore all chaos components
	@echo "🚑 Removing any active KEDA pause annotations..."
	@$(DOCKER) exec -it k8s-toolbox kubectl annotate scaledobject fastapi-scaler -n backend autoscaling.keda.sh/paused-replicas- 2>/dev/null || true
	@$(DOCKER) exec -it k8s-toolbox kubectl annotate scaledobject trade-writer-scaler -n backend autoscaling.keda.sh/paused-replicas- 2>/dev/null || true
	@echo "▶️  Resuming Flux reconciliations..."
	@$(DOCKER) exec -it k8s-toolbox flux resume kustomization 2-data 2>/dev/null || true
	@$(DOCKER) exec -it k8s-toolbox flux resume kustomization 3-apps 2>/dev/null || true
	@echo "🔄 Forcing a Flux sync to immediately recover replica counts..."
	@$(MAKE) --no-print-directory sync LAYER=all
	@echo "📦 Forcing HelmRelease reconciliations (to restore Redis/StatefulSets)..."
	@$(DOCKER) exec -it k8s-toolbox flux reconcile helmrelease -n data --all 2>/dev/null || true

chaos-node-stop: ## 🔥 Stopping the primary K3s node (Simulating Server Crash)
	@echo "🔥 Stopping the primary K3s node (Simulating Server Crash)..."
	@$(DOCKER) exec -it k8s-toolbox k3d node stop k3d-dev-cluster-server-0

chaos-node-start: ## 🚑 Rebooting the primary K3s node
	@echo "🚑 Rebooting the primary K3s node..."
	@$(DOCKER) exec -it k8s-toolbox k3d node start k3d-dev-cluster-server-0
