import os
from pathlib import Path

import logbook

# 1. Define the log directory
# This must match the path you mapped in your k3d-config.yaml
LOG_DIR = Path("../../logs")
LOG_FILE = LOG_DIR / "app.log"

# 2. Ensure directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 3. Setup the FileHandler
# 'format_string' mimics standard log formats so Loki parses it easily
file_handler = logbook.FileHandler(
    LOG_FILE, 
    level='INFO', 
    format_string='[{record.time:%Y-%m-%d %H:%M:%S}] {record.level_name}: {record.channel}: {record.message}'
)

# 4. Push the handler onto the stack
file_handler.push_application()

# 5. Usage example
log = logbook.Logger('booklib')

def test_log():
    log.info("FastAPI service is starting up...")
    log.warning("This is a warning log to test the bridge.")
    log.error("This is an error log to test the bridge.")

if __name__ == "__main__":
    test_log()
    print(f"Log written to {LOG_FILE}")
