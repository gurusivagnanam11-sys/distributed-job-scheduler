"""
Custom logging configuration for structured JSON output.
"""
import logging
import json
from datetime import datetime, timezone

from app.core.config import settings

class JSONFormatter(logging.Formatter):
    """
    Minimal custom logging Formatter to emit JSON logs.
    Includes base fields (timestamp, level, message, logger_name) 
    and specific extra fields if they are present on the LogRecord.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Include specific extra fields if present
        for field in ("job_id", "worker_id", "queue_id", "attempt"):
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)

        # Include exception trace if any
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)

def setup_logging():
    """Configure root logger based on LOG_FORMAT setting."""
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    
    # Default to text for local dev, use json if configured
    log_format = getattr(settings, "LOG_FORMAT", "text").lower()
    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        # Standard text format
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
