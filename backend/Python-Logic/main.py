import os
import random
import time
from pathlib import Path

import logbook

# 1. Define the base log directory
LOG_DIR = Path("../../logs")
APPS = ["FastAPI", "Postgres", "Redis", "Streamlit"]

# A dictionary to hold our different loggers
loggers = {}

# 2. Setup folders and handlers for each app dynamically
for app_name in APPS:
    # Create the specific subfolder (e.g., ../../logs/FastAPI)
    app_dir = LOG_DIR / app_name
    app_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = app_dir / "app.log"
    
    # Create a handler specifically for this app
    # The `filter` lambda ensures this file ONLY gets logs from its matching channel
    handler = logbook.FileHandler(
        log_file, 
        level='INFO', 
        format_string='[{record.time:%Y-%m-%d %H:%M:%S}] {record.level_name}: {record.channel}: {record.message}',
        filter=lambda record, _handler, target=app_name: record.channel == target
    )
    
    # Push this handler to the global stack
    handler.push_application()
    
    # Create the logger and store it in our dictionary
    loggers[app_name] = logbook.Logger(app_name)

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
    for i in range(20):
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
    print("\n✅ Finished generating random logs!")
