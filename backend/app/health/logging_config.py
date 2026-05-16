"""Structured JSON logging configuration for the AI Marketing Platform.

Provides async-safe, correlation-ID-aware JSON logging with environment-based
log levels and sensitive data redaction.

Usage:
    from app.health.logging_config import configure_logging, get_logger

    configure_logging()
    logger = get_logger("aimp.services")
    logger.info({"event": "startup", "port": 8000})

The logger accepts either dict payloads (preferred for structured logging)
or plain strings for simple messages.
"""

import json
import logging
import logging.config
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

# ---------------------------------------------------------------------------
# Environment-aware log level
# ---------------------------------------------------------------------------

_ENV = os.environ.get("ENVIRONMENT", "development").lower()
_LOG_LEVEL_MAP = {
    "production": logging.WARNING,
    "staging": logging.INFO,
    "development": logging.DEBUG,
    "test": logging.DEBUG,
}

# Default log level per module in production
_MODULE_LEVELS: Dict[str, int] = {
    "aimp.http": logging.INFO,
    "aimp.errors": logging.WARNING,
    "aimp.db": logging.WARNING,
    "aimp.redis": logging.WARNING,
    "aimp.ai": logging.INFO,
    "aimp.erp": logging.INFO,
    "aimp.celery": logging.INFO,
    "uvicorn": logging.INFO,
    "uvicorn.access": logging.WARNING,
    "sqlalchemy.engine": logging.WARNING,
}


# ---------------------------------------------------------------------------
# JSON Formatter
# ---------------------------------------------------------------------------


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging.

    Outputs log records as JSON objects with standard fields:
    - timestamp: ISO 8601 timestamp in UTC
    - level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - logger: Logger name
    - message: Log message or structured payload
    - correlation_id: Request correlation ID if available
    - source: File and line number
    - thread: Thread identifier
    - exception: Exception info if present

    Usage with logging config:
        formatter = JSONFormatter()
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    """

    # Fields to redact from log payloads
    SENSITIVE_KEYS = {
        "password",
        "token",
        "api_key",
        "apikey",
        "secret",
        "access_token",
        "refresh_token",
        "jwt",
        "authorization",
        "cookie",
    }

    def __init__(self, indent: Optional[int] = None) -> None:
        super().__init__()
        self.indent = indent

    def _redact_sensitive(self, obj: Any) -> Any:
        """Recursively redact sensitive keys from dict payloads.

        Args:
            obj: Object to redact (dict, list, or scalar).

        Returns:
            Object with sensitive values replaced.
        """
        if isinstance(obj, dict):
            result: Dict[str, Any] = {}
            for key, value in obj.items():
                if key.lower() in self.SENSITIVE_KEYS:
                    result[key] = "***"
                else:
                    result[key] = self._redact_sensitive(value)
            return result
        elif isinstance(obj, list):
            return [self._redact_sensitive(item) for item in obj]
        return obj

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record: Standard logging LogRecord.

        Returns:
            JSON string representation of the log record.
        """
        # Build structured log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }

        # Handle message - can be dict (structured) or string
        message = record.getMessage()
        if isinstance(record.msg, dict):
            log_entry["message"] = self._redact_sensitive(record.msg)
        elif message.startswith("{") and message.endswith("}"):
            # Try to parse as JSON
            try:
                parsed = json.loads(message)
                log_entry["message"] = self._redact_sensitive(parsed)
            except json.JSONDecodeError:
                log_entry["message"] = message
        else:
            log_entry["message"] = message

        # Add correlation ID if present
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Source location
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Exception info
        if record.exc_info and record.exc_info[0]:
            exc_type, exc_value, exc_tb = record.exc_info
            log_entry["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc_value) if exc_value else None,
                "traceback": traceback.format_exception(*record.exc_info) if exc_tb else None,
            }

        # Extra fields from record
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
                "correlation_id",
            ):
                log_entry[key] = self._redact_sensitive(value)

        if self.indent:
            return json.dumps(log_entry, ensure_ascii=False, indent=self.indent, default=str)
        return json.dumps(log_entry, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Correlation ID Filter
# ---------------------------------------------------------------------------


class CorrelationIdFilter(logging.Filter):
    """Inject correlation_id into log records from context.

    Use with context variables or thread-local storage to propagate
    correlation IDs through async code.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id from context to the log record.

        Looks for correlation_id in contextvars first, then in
        a thread-local fallback.

        Args:
            record: LogRecord to augment.

        Returns:
            True (never filters out records).
        """
        try:
            import contextvars
            cid_var = contextvars.ContextVar("correlation_id", default=None)
            cid = cid_var.get(None)
            if cid:
                record.correlation_id = cid  # type: ignore[attr-defined]
        except Exception:
            pass
        return True


# ---------------------------------------------------------------------------
# Log adapter that supports dict messages
# ---------------------------------------------------------------------------


class StructuredLogger(logging.LoggerAdapter):
    """Logger adapter that supports dict payloads and correlation IDs.

    Usage:
        logger = get_logger("aimp.services")
        logger.info({"event": "user_login", "user_id": "123"})
        logger.error("Plain string also works")
    """

    def process(
        self, msg: Any, kwargs: Dict[str, Any]
    ) -> tuple[Any, Dict[str, Any]]:
        """Process log message before emission.

        Injects extra fields from the adapter's extra dict.

        Args:
            msg: Log message (str or dict).
            kwargs: Keyword arguments for the log call.

        Returns:
            Tuple of (message, kwargs) with extras merged.
        """
        extra = kwargs.get("extra", {})
        if self.extra:
            merged = dict(self.extra)
            merged.update(extra)
            kwargs["extra"] = merged
        return msg, kwargs

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_dict(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_dict(logging.INFO, msg, args, **kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_dict(logging.WARNING, msg, args, **kwargs)

    def error(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_dict(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg: Any, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        self._log_with_dict(logging.CRITICAL, msg, args, **kwargs)

    def _log_with_dict(self, level: int, msg: Any, args: Any, **kwargs: Any) -> None:
        """Internal method to handle dict messages.

        Converts dict payloads to JSON strings so the formatter can
        parse them back into structured output.

        Args:
            level: Log level.
            msg: Message (dict or string).
            args: Positional args (unused for dict messages).
            **kwargs: Extra kwargs for the log call.
        """
        if isinstance(msg, dict):
            msg = json.dumps(msg, ensure_ascii=False, default=str)
            args = ()  # Drop args when msg is a dict
        self.log(level, msg, *args, **kwargs)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


_configure_logging_done = False


def configure_logging(
    log_level: Optional[Union[int, str]] = None,
    indent: Optional[int] = None,
) -> None:
    """Configure structured JSON logging for the application.

    Sets up console logging with the JSONFormatter.  Safe to call
    multiple times -- subsequent calls are no-ops.

    Args:
        log_level: Override the default log level.  If None, uses
            environment-based level (DEBUG for dev, WARNING for prod).
        indent: JSON indentation level.  If None, outputs compact JSON.
    """
    global _configure_logging_done
    if _configure_logging_done:
        return
    _configure_logging_done = True

    # Determine log level
    if log_level is None:
        env_level = os.environ.get("LOG_LEVEL", "").upper()
        if env_level:
            log_level = getattr(logging, env_level, logging.INFO)
        else:
            log_level = _LOG_LEVEL_MAP.get(_ENV, logging.INFO)
    elif isinstance(log_level, str):
        log_level = getattr(logging, log_level.upper(), logging.INFO)

    # Uvicorn formatter in dev should be plain text for readability
    use_json = _ENV in ("production", "staging")

    if use_json:
        formatter: logging.Formatter = JSONFormatter(indent=indent)
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.addHandler(console_handler)
    root_logger.setLevel(log_level)

    # Set module-specific levels in production
    for module_name, level in _MODULE_LEVELS.items():
        if _ENV == "production":
            logging.getLogger(module_name).setLevel(level)
        else:
            logging.getLogger(module_name).setLevel(log_level)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if os.environ.get("SQLALCHEMY_ECHO") == "1" else logging.WARNING
    )

    get_logger("aimp.logging").info({
        "event": "logging_configured",
        "environment": _ENV,
        "log_level": logging.getLevelName(log_level),
        "json_format": use_json,
    })


def get_logger(name: str, extra: Optional[Dict[str, Any]] = None) -> StructuredLogger:
    """Get a structured logger with the given name.

    Args:
        name: Logger namespace (use ``aimp.<module>`` convention).
        extra: Default extra fields to include with every log entry.

    Returns:
        StructuredLogger instance ready for dict or string messages.

    Example:
        logger = get_logger("aimp.services.campaign")
        logger.info({"event": "campaign_created", "campaign_id": "123"})
    """
    base_logger = logging.getLogger(name)
    return StructuredLogger(base_logger, extra or {})
