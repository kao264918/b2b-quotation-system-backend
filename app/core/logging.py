"""
Structured JSON Logging Configuration
Provides JSON-formatted logging with request ID injection.
"""
import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.request_id import get_request_id


class JsonFormatter(logging.Formatter):
    """
    Custom formatter that outputs log records as JSON.
    Includes request_id from context when available.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request_id if available
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class RequestContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes request context.
    """

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra_fields = extra.get("extra_fields", {})
        
        # Merge any additional fields
        if self.extra:
            extra_fields.update(self.extra)
        
        extra["extra_fields"] = extra_fields
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(log_level: str = "INFO", json_format: bool = True) -> None:
    """
    Configure application-wide logging.
    
    Args:
        log_level: The minimum log level to output.
        json_format: If True, output logs as JSON. If False, use standard format.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if json_format:
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> RequestContextAdapter:
    """
    Get a logger with request context support.
    
    Args:
        name: The name of the logger (usually __name__).
    
    Returns:
        A logger adapter that automatically includes request context.
    """
    logger = logging.getLogger(name)
    return RequestContextAdapter(logger, {})
