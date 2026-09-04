import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


from contextvars import ContextVar

# ContextVar for request-scoped correlation ID
_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id_ctx", default=None)


def set_request_id(request_id: Optional[str]) -> None:
    """Sets the correlation request ID in the current async context."""
    _request_id_ctx.set(request_id)


def get_request_id() -> Optional[str]:
    """Retrieves the correlation request ID from the current async context."""
    return _request_id_ctx.get()


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno,
        }

        # Include custom extra fields or context-propagated request_id
        rid = getattr(record, "request_id", None) or get_request_id()
        if rid:
            log_obj["request_id"] = rid
        if hasattr(record, "merchant_id"):
            log_obj["merchant_id"] = record.merchant_id
        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_obj.update(record.extra_data)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(level: int = logging.INFO) -> None:
    """Configures structured JSON logging globally for the application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Gets a logger instance."""
    return logging.getLogger(name or "risk_engine")
