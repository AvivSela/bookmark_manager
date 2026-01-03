import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context fields."""

    def __init__(self, *args: Any, service_name: str = "unknown", **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.service_name = service_name

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to the log record."""
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["service"] = self.service_name
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["timestamp"] = self.formatTime(record, self.datefmt)

        # Add request context if available (from request state)
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id
        if hasattr(record, "tenant_id"):
            log_record["tenant_id"] = record.tenant_id


def setup_json_logging(service_name: str, log_level: str = "INFO") -> None:
    """
    Configure structured JSON logging for the service.

    Args:
        service_name: Name of the service (e.g., "bookmark-service")
        log_level: Logging level (default: INFO)
    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(service)s %(logger)s %(message)s",
        service_name=service_name,
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Set log level for third-party libraries to reduce noise
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiokafka").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)
