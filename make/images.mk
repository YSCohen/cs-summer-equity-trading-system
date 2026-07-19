.PHONY: update-ui update-api clean-images

# ==========================================
# 🐳 IMAGE BUILDING & CLEANUP
# ==========================================

update-ui: ## Rebuild UI docker image, import to k3d, clear cache, and restart UI
	@echo "🚀 Rebuilding web-ui docker image..."
	$(DOCKER) build -t web-ui-image:dev-sean ./web-ui
	@echo "🧹 Cleaning up dangling host layers..."
	$(DOCKER) image prune -f
	@echo "📦 Importing image into k3d..."
	$(DOCKER) exec k8s-toolbox k3d image import web-ui-image:dev-sean -c dev-cluster
	@echo "♻️  Restarting frontend pods to apply new image..."
	$(MAKE) --no-print-directory kubectl CMD="delete pod -n frontend -l app=streamlit"
	@echo "✅ Done!"

update-api: ## Rebuild API docker image, import to k3d, clear cache, and restart API
	@echo "🚀 Rebuilding api docker image..."
	$(DOCKER) build -t api-image:dev-sean ./api
	@echo "🧹 Cleaning up dangling host layers..."
	$(DOCKER) image prune -f
	@echo "📦 Importing image into k3d..."
	$(DOCKER) exec k8s-toolbox k3d image import api-image:dev-sean -c dev-cluster
	@echo "♻️  Restarting backend pods to apply new image..."
	$(MAKE) --no-print-directory kubectl CMD="delete pod -n backend -l app=fastapi"
	@echo "✅ Done!"

clean-images: ## Aggressively clean docker host images and k3d image cache
	@echo "🧹 Pruning unused host docker images..."
	$(DOCKER) image prune -a -f
	@echo "🧹 Pruning unused containerd images inside k3d..."
	-$(DOCKER) exec k3d-dev-cluster-agent-0 crictl rmi --prune
	-$(DOCKER) exec k3d-dev-cluster-agent-1 crictl rmi --prune
	-$(DOCKER) exec k3d-dev-cluster-server-0 crictl rmi --prune
	@echo "✅ Done!"
