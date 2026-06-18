import random
import time
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# 1. Define the base log directory
LOG_DIR = Path("../../logs")
APPS = ["FastAPI", "Postgres", "Redis", "Streamlit"]

# 2. Custom Formatter to strictly enforce New York time
class NYTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # Convert the log record's internal timestamp strictly to America/New_York
        dt = datetime.fromtimestamp(record.created, tz=ZoneInfo("America/New_York"))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

# A dictionary to hold our different loggers
loggers = {}

# 3. Setup folders and standard handlers for each app dynamically
for app_name in APPS:
    # Create the specific subfolder
    app_dir = LOG_DIR / app_name
    app_dir.mkdir(parents=True, exist_ok=True)
    log_file = app_dir / "app.log"
    
    # Get standard Python logger for this specific app
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.INFO)
    
    # Prevent logs from bubbling up to the root console logger
    logger.propagate = False 
    
    # Clear any existing handlers (useful if running in interactive environments)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    # Set up the file handler
    handler = logging.FileHandler(log_file)
    
    # Apply the exact format Loki expects using our New York Formatter
    # This outputs: [2026-06-17 14:30:00] INFO: FastAPI: Message...
    formatter = NYTimeFormatter('[{asctime}] {levelname}: {name}: {message}', style='{')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    loggers[app_name] = logger

def test_log():
    print(f"Starting log simulation in {LOG_DIR.resolve()}...")
    
    sample_messages = [
        "Connection established successfully.",
        "Timeout occurred while waiting for response.",
        "User authentication failed.",
        "Data synchronization complete.",
        "Memory usage spike detected.",
        "Query execution took too long."
    ]

    # Generate 20 random logs
    for _ in range(20):
        # "Flip a coin" to pick a random app and a random log level
        target_app = random.choice(APPS)
        target_level = random.choice(['info', 'warning', 'error'])
        
        logger = loggers[target_app]
        msg = random.choice(sample_messages)
        
        # Log it at the randomly chosen level
        if target_level == 'info':
            logger.info(msg)
        elif target_level == 'warning':
            logger.warning(msg)
        elif target_level == 'error':
            logger.error(msg)
            
        print(f"Logged {target_level.upper()} to {target_app}/app.log")
        time.sleep(0.2) # Add a tiny delay so timestamps aren't perfectly identical

if __name__ == "__main__":
    test_log()
    print("\n✅ Finished generating random logs in NY Timezone!")
