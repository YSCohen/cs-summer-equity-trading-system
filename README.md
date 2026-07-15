# Equity Trading System

Welcome to the heart of our operations! This repository contains the entire infrastructure and application stack for our high-frequency Equity Trading System.

### The Stack
We run a modern, containerized stack designed for speed and reliability:
* **API**: FastAPI (Python) with `uv` package management.
* **UI**: Streamlit (Python) featuring interactive AG Grid tables for mass trading and rapid data visualization.
* **Workers**: Rust-based syncers (`db-syncer`, `trade-writer`, `price-cacher`, `redis-populator`) for ultra-fast data handling.
* **Data Layer**: Redis with Redis Sentinel (HA/high-speed ingestion), PostgreSQL for persistence (HA via CloudNativePG), PgBouncer for connection pooling, and UI management via Adminer & RedisInsight.
* **Autoscaling & Ingress**: KEDA (Kubernetes Event-driven Autoscaling) for HPA, Traefik for ingress, and Reloader for dynamic config updates.
* **Testing**: Locust for distributed load testing and `make chaos` for chaos engineering.
* **Infrastructure**: Kubernetes (k3d for local dev, K3s for distributed remote), Flux for GitOps, and the Loki-stack for observability.

### Getting Started
Ready to jump in? Check out our [DEVELOPERS.md](DEVELOPERS.md) for a deep dive into how to set up your environment, manage overlays, and debug the cluster.

#### K3S Manager option
You can clone our k3s manager here 
```sh 
curl -sSL "https://raw.githubusercontent.com/SM26-Industrial-Software-Dev/equity-trading-system/main/k3s_manager.sh" -o k3s_manager.sh && chmod +x k3s_manager.sh
```

