---
# Developer Guide

Welcome to the team! This guide covers everything you need to build, run, and debug the Equity Trading System.

> **Note:** We prefer using the `Makefile` wrappers for all cluster operations. If you don't have `make` installed, you can use `./cluster_up.sh` as a direct fallback.

---

## 1. Environment Setup & Overlays
Every developer has their own namespace (e.g., `dev-sean`, `dev-max`). This allows you to work in your own isolated area of the cluster.

### How to use your Overlay:
1. **Push to GitHub**: Flux only reconciles what is in the repository. **Always `git push` your changes** to your branch before they appear in the cluster.
2. **Changing Images**: If you want to use a personal image instead of the organization's default, edit the `kustomization.yaml` inside your specific overlay directory (`k8s/manifests/overlays/dev-<name>/`). 
   * Uncomment the `images` section.
   * Update the `newName` to point to your specific container registry.
   * Run `make sync` to trigger a Flux reconciliation.
3. **Overwriting**: You can overwrite any base configuration (resources, replicas, env vars) in your `kustomization.yaml`.

---

## 2. The "Make" Toolbox (Debugging)
Stop trying to memorize complex `kubectl` commands. We have mapped everything to the `Makefile`.

* **See all available commands**: Run `make help` to see the full list of targets and descriptions.
* **Check System Health**:
    * `make status`: View the status of all pods across all namespaces.
    * `make status-wide`: View pod status with node/IP details.
* **Direct Access**: 
    * `make shell-api` / `make shell-ui`: Hop into a container shell if you need to inspect files.
    * `make psql`: Jump straight into the Postgres console.
    * `make redis-cli`: Open the Redis CLI.
* **Database Operations**:
    * `make db-backup`: Takes a full snapshot of the Postgres trading database and saves it to the project root.
    * `make db-restore`: Wipes the database and interactively restores it from a selected snapshot file.
    * `make db-clear`: Wipes the entire database cleanly and rebuilds the Redis caches.
* **Chaos & Restarting**:
    * `make bounce`: Interactive menu to safely restart any deployment.
    * `make chaos`: Interactive menu to scale components down to 0 to simulate failures.

---

## 3. Logging & Observability
We use **Loki** to aggregate logs. 

### Standard Output (stdout) Requirements
* **Everything must be JSON**: If you are logging to `stdout`, your logs must be serialized as **JSON**. Our collectors parse JSON logs automatically for Grafana.
* **Push URL**: If you need to push logs manually, the endpoint is: `http://loki-stack.monitoring.svc.cluster.local:3100/loki/api/v1/push`

### Debugging Logs in Grafana
* **URL**: `http://grafana.localhost:8080`
* **Workflow**: Check the logs via `make logs-api` or `make logs-ui` before heading to the Grafana dashboard to query the error history.

---

## 4. Need Help?
* **Flux Stuck?**: If your changes aren't appearing, run `make sync`. This forces Flux to reconcile the stack with the repository immediately.
* **Load Testing**: Use `./locust_reload.sh` to sync your local `locustfile.py` changes to the cluster without waiting for the full GitOps cycle.

---

## 5. Remote Development & Tailscale

### K3S Manager
If you need to deploy and manage a distributed remote cluster, use the interactive manager script:
```sh 
curl -sSL "https://raw.githubusercontent.com/SM26-Industrial-Software-Dev/equity-trading-system/main/k3s_manager.sh" -o k3s_manager.sh && chmod +x k3s_manager.sh
```

### Tailscale Kubernetes Operator
To connect the cluster securely to the Tailnet, the K3s environment uses the Tailscale Kubernetes Operator. 
This requires an OAuth client ID and secret to be provisioned in the Tailscale Admin Console and injected into the cluster as a secret (`operator-oauth` in the `tailscale` namespace).

**Required Tailscale OAuth Permissions (Scopes):**
When generating the OAuth client in Tailscale, you must grant it the following permissions:

| Permission / Scope | Access Level | Tags Applied |
| :--- | :--- | :--- |
| **DNS** | Write | |
| **Services** | Write | `tag:k8s-operator` |
| **Core** | Write | `tag:k8s-operator` |
| **Routes** | Write | |
| **Device invites** | Write | |
| **Auth keys** | Write | `tag:k8s-operator` |
