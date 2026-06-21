# 🪵 Developer Logging Guide

Welcome to the local logging environment! We use a local Kubernetes cluster (K3d) running the **Grafana + Loki + Promtail** stack to collect, parse, and visualize logs from everyone's local microservices.

You **do not** need to install Kubernetes or understand Helm to use this. You just need Docker installed and running.

## 🚀 1. Quick Start

To spin up the logging environment without booting up the entire backend API, navigate to the `backend/k8s` directory and run:

`cd backend/k8s`
`make logs-rebuild`

> ⚠️ **IMPORTANT: BE PATIENT!** > Kubernetes takes about **1 to 2 minutes** to fully pull the images, initialize the Loki database, and start the Grafana web server. If the page doesn't load immediately, grab a coffee and refresh in a minute!

## 📊 2. Accessing Grafana

Once the cluster is up, Grafana is accessible via your browser. Because of how our local load balancer is configured, you must specify **port 8080**.

* **URL:** <http://grafana.localhost:8080> *(or <http://localhost:8080>)*
* **Username:** `admin`
* **Password:** `Rust!`

Navigate to **Dashboards -> k3d Stats** to view the live log feeds.

*(Note: When you first generate a log, it might take 5–10 seconds for Promtail to detect the new file and push it to Grafana. Subsequent logs will appear instantly).*

## 📝 3. How to Write Your Logs

Our logging pipeline is highly automated, but it relies on **strict conventions**. Promtail watches the `logs/` folder at the root of this repository.

To ensure your logs appear correctly on the dashboard panels, you must follow these two rules:

### Rule 1: The Folder Structure (The `app` tag)

You **must** use one of the pre-configured subfolders inside the root `logs/` directory. Our Grafana dashboard is specifically hardcoded to look for these exact application paths. Promtail reads this folder name and turns it into the `{app}` label in Grafana.

✅ **ALLOWED FOLDERS:**

* `logs/FastAPI/app.log`
* `logs/Postgres/db.log`
* `logs/Redis/cache.log`
* `logs/Streamlit/ui.log`

❌ **DO NOT DO THIS:**

* `logs/fastapi_app.log` *(Will not get tagged correctly!)*
* `logs/my_custom_folder/app.log` *(Will not show up on the dashboard!)*

### Rule 2: The Log Format (The `level` tag)

Our pipeline uses Regex to extract the severity level from your log text. Your logs **must** start with a bracketed timestamp, followed by a space, followed by an uppercase level (`INFO`, `WARNING`, `ERROR`), and a colon.

**Required Format:**
`[YYYY-MM-DD HH:MM:SS] LEVEL: Message`

**Example (Python Logbook):**
If you are using Python, configure your FileHandler format string exactly like this:

`import logbook`
`from pathlib import Path`

`# 1. Point to your specific subfolder!`
`LOG_FILE = Path("../../logs/Streamlit/app.log")`
`LOG_FILE.parent.mkdir(parents=True, exist_ok=True)`

`# 2. Use this exact format string`
`file_handler = logbook.FileHandler(`
` LOG_FILE, `
` level='INFO', `
`format_string='[{record.time:%Y-%m-%d %H:%M:%S}] {record.level_name}: {record.channel}: {record.message}'`
`)`
`file_handler.push_application()`

If you follow the folder structure and log format, your logs will automatically appear in the correct dashboard panel with full filtering support.

## ⏱️ 4. Using the Grafana Dashboard

Once you are on the **k3d Stats** dashboard, you can control how the data is displayed:

* **Manual Refreshing:** The dashboard is configured to automatically pull new logs every 5 seconds. However, if you want an instant update, click the **Refresh icon (circular arrows)** in the top right corner of the UI.
* **Changing the Time Range:** By default, Grafana might only show logs from a narrow recent window. If you don't see a clock icon, look for text in the top right corner that says **"Last 15 minutes"** or **"now-15m"**. Click that text to expand your search window to look at logs from the last hour, day, or a specific date range.
