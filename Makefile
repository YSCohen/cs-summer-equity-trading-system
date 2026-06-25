.PHONY: all help
all: help

DOCKER   ?= docker
HOST_ROOT := $(shell pwd)
export HOST_ROOT

# Include all of our modular Make targets
include backend/k8s/make/cluster.mk
include backend/k8s/make/status.mk
include backend/k8s/make/debug.mk
include backend/k8s/make/chaos.mk
include backend/k8s/make/logs.mk

# ==========================================
# 🆘 HELP MENU
# ==========================================

help: ## Show this dynamic help menu
	@echo "=========================================================="
	@echo "🚀 EQUITY TRADING SYSTEM - DEVELOPER TOOLBOX"
	@echo "=========================================================="
	@echo "Usage: make [target]"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
