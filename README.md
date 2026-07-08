# Equity Trading System

Welcome to the heart of our operations! This repository contains the entire infrastructure and application stack for our high-frequency Equity Trading System.

### The Stack
We run a modern, containerized stack designed for speed and reliability:
* **API**: FastAPI (Python) with `uv` package management.
* **UI**: Streamlit (Python) for rapid data visualization.
* **Workers**: Rust-based syncers (`db-syncer`, `trade-writer`, `redis-populator`) for ultra-fast data handling.
* **Data Layer**: Redis for ingestion, PostgreSQL for persistence, and PgBouncer for connection pooling.
* **Infrastructure**: Kubernetes (k3d), Flux for GitOps, and the Loki-stack for observability.

### Getting Started
Ready to jump in? Check out our [DEVELOPERS.md](DEVELOPERS.md) for a deep dive into how to set up your environment, manage overlays, and debug the cluster.

#### K3S Manager option
You can clone our k3s manager here 
```sh 
curl -sSL "https://raw.githubusercontent.com/SM26-Industrial-Software-Dev/equity-trading-system/main/k3s_manager.sh" -o k3s_manager.sh && chmod +x k3s_manager.sh
```
