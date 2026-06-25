import logbook
import sys

try:
    stream_handler = logbook.StreamHandler(
        sys.stdout,
        level="INFO",
        format_string="[{record.time:%Y-%m-%d %H:%M:%S}] {record.level_name}: {record.channel}: {record.message}",
    )

    stream_handler.push_application()

except Exception as e:
    print(f"LOGGING FAILED: {e}")
    raise

logger = logbook.Logger("FastAPI")
