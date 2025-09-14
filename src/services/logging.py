"""
Structured JSON logging configuration for production observability.
"""

import json
import logging
import logging.config
import os
import sys
import traceback
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Optional

import structlog
from fastapi import Request
from structlog.processors import JSONRenderer


class ProductionFormatter(logging.Formatter):
    """Custom JSON formatter for production logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""

        # Base log data
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add thread and process info
        log_data.update(
            {
                "thread": record.thread,
                "thread_name": record.threadName,
                "process": record.process,
            }
        )

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields from logger
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "exc_info",
                "exc_text",
                "stack_info",
                "getMessage",
            ]:
                extra_fields[key] = value

        if extra_fields:
            log_data["extra"] = extra_fields

        return json.dumps(log_data, default=str)


class RequestContextFilter(logging.Filter):
    """Add request context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request context if available."""

        # Try to get request context from contextvars
        try:
            request_context = get_request_context()
            if request_context:
                record.request_id = request_context.get("request_id")
                record.user_id = request_context.get("user_id")
                record.endpoint = request_context.get("endpoint")
                record.method = request_context.get("method")
        except:
            pass

        return True


class PerformanceFilter(logging.Filter):
    """Filter and enhance performance-related logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add performance metadata to logs."""

        if hasattr(record, "duration_ms"):
            # Categorize performance
            if record.duration_ms > 1000:
                record.performance_category = "slow"
            elif record.duration_ms > 500:
                record.performance_category = "medium"
            else:
                record.performance_category = "fast"

        return True


# Request context storage
_request_context: dict[str, Any] = {}


def set_request_context(context: dict[str, Any]) -> None:
    """Set request context for logging."""
    global _request_context
    _request_context = context


def get_request_context() -> dict[str, Any]:
    """Get current request context."""
    return _request_context.copy()


@contextmanager
def request_context(request_id: Optional[str] = None, **context: Any) -> Any:
    """Context manager for request-scoped logging."""
    if not request_id:
        request_id = str(uuid.uuid4())

    old_context = _request_context.copy()
    new_context = {"request_id": request_id, **context}
    set_request_context(new_context)

    try:
        yield new_context
    finally:
        set_request_context(old_context)


def configure_logging(
    level: str = "INFO",
    format_type: str = "json",
    enable_request_context: bool = True,
    enable_performance_logging: bool = True,
    log_file: str | None = None,
) -> None:
    """Configure application logging."""

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            JSONRenderer() if format_type == "json" else structlog.processors.KeyValueRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Logging configuration
    handlers = {}
    formatters = {}

    if format_type == "json":
        formatters["json"] = {
            "()": ProductionFormatter,
        }
    else:
        formatters["standard"] = {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"}  # type: ignore[dict-item]

    # Console handler
    handlers["console"] = {
        "class": "logging.StreamHandler",
        "formatter": "json" if format_type == "json" else "standard",
        "stream": sys.stdout,
    }

    # File handler if specified
    if log_file:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_file,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "json" if format_type == "json" else "standard",
        }

    # Filters
    filters: dict[str, Any] = {}
    if enable_request_context:
        filters["request_context"] = {
            "()": RequestContextFilter,
        }

    if enable_performance_logging:
        filters["performance"] = {
            "()": PerformanceFilter,
        }

    # Complete logging configuration
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "filters": filters,
        "handlers": handlers,
        "loggers": {
            "": {  # Root logger
                "handlers": list(handlers.keys()),
                "level": level,
                "filters": list(filters.keys()),
            },
            "uvicorn": {
                "handlers": list(handlers.keys()),
                "level": level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": list(handlers.keys()),
                "level": level,
                "propagate": False,
            },
            "fastapi": {
                "handlers": list(handlers.keys()),
                "level": level,
                "propagate": False,
            },
            "sqlalchemy": {
                "handlers": list(handlers.keys()),
                "level": "WARNING",  # Reduce SQL noise
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "handlers": list(handlers.keys()),
                "level": "WARNING",
                "propagate": False,
            },
            "aioboto3": {
                "handlers": list(handlers.keys()),
                "level": "WARNING",  # Reduce AWS SDK noise
                "propagate": False,
            },
            "botocore": {
                "handlers": list(handlers.keys()),
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> Any:  # structlog.BoundLogger
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_performance(logger: logging.Logger, operation: str, duration_ms: float, **extra_data: Any) -> None:
    """Log performance metrics."""
    logger.info(
        f"{operation} completed",
        extra={
            "operation": operation,
            "duration_ms": duration_ms,
            "performance_log": True,
            **extra_data,
        },
    )


def log_api_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
    request_size: Optional[int] = None,
    response_size: Optional[int] = None,
) -> None:
    """Log API request details."""
    logger.info(
        f"{method} {path} - {status_code}",
        extra={
            "api_request": True,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "request_size_bytes": request_size,
            "response_size_bytes": response_size,
        },
    )


def log_database_operation(
    logger: logging.Logger,
    operation: str,
    table: str,
    duration_ms: float,
    rows_affected: Optional[int] = None,
    **extra_data: Any,
) -> None:
    """Log database operation details."""
    logger.info(
        f"Database {operation} on {table}",
        extra={
            "database_operation": True,
            "operation": operation,
            "table": table,
            "duration_ms": duration_ms,
            "rows_affected": rows_affected,
            **extra_data,
        },
    )


def log_storage_operation(
    logger: logging.Logger,
    operation: str,
    object_key: str,
    duration_ms: float,
    size_bytes: Optional[int] = None,
    **extra_data: Any,
) -> None:
    """Log storage operation details."""
    logger.info(
        f"Storage {operation}: {object_key}",
        extra={
            "storage_operation": True,
            "operation": operation,
            "object_key": object_key,
            "duration_ms": duration_ms,
            "size_bytes": size_bytes,
            **extra_data,
        },
    )


def log_authentication_event(
    logger: logging.Logger,
    event_type: str,
    user_id: Optional[str] = None,
    token_type: Optional[str] = None,
    success: bool = True,
    **extra_data: Any,
) -> None:
    """Log authentication events."""
    level = logging.INFO if success else logging.WARNING

    logger.log(
        level,
        f"Authentication {event_type}" + (" successful" if success else " failed"),
        extra={
            "authentication_event": True,
            "event_type": event_type,
            "user_id": user_id,
            "token_type": token_type,
            "success": success,
            **extra_data,
        },
    )


def log_error(logger: logging.Logger, error: Exception, context: Optional[str] = None, **extra_data: Any) -> None:
    """Log error with full context."""
    logger.error(
        f"Error in {context}: {str(error)}" if context else str(error),
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            **extra_data,
        },
        exc_info=True,
    )


class LoggingMiddleware:
    """FastAPI middleware for request logging."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("api.requests")

    async def __call__(self, request: Request, call_next: Any) -> Any:
        """Log API requests and responses."""
        request_id = str(uuid.uuid4())
        start_time = datetime.now(UTC)

        # Set request context
        with request_context(
            request_id=request_id,
            method=request.method,
            endpoint=str(request.url.path),
            user_id=getattr(request.state, "user_id", None),
        ):
            # Log request start
            self.logger.info(
                f"Request started: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "user_agent": request.headers.get("user-agent"),
                    "client_ip": request.client.host if request.client else None,
                    "request_start": True,
                },
            )

            try:
                # Process request
                response = await call_next(request)

                # Calculate duration
                end_time = datetime.now(UTC)
                duration_ms = (end_time - start_time).total_seconds() * 1000

                # Log successful response
                log_api_request(
                    self.logger,
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                    user_id=getattr(request.state, "user_id", None),
                )

                return response

            except Exception as e:
                # Calculate duration
                end_time = datetime.now(UTC)
                duration_ms = (end_time - start_time).total_seconds() * 1000

                # Log error
                log_error(
                    self.logger,
                    e,
                    context=f"{request.method} {request.url.path}",
                    request_id=request_id,
                    duration_ms=duration_ms,
                )

                raise


# Initialize logging based on environment
def init_logging() -> None:
    """Initialize logging configuration based on environment."""

    # Get configuration from environment variables
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "json").lower()
    log_file = os.getenv("LOG_FILE")

    # Configure logging
    configure_logging(
        level=log_level,
        format_type=log_format,
        enable_request_context=True,
        enable_performance_logging=True,
        log_file=log_file,
    )

    # Set up basic loggers
    logger = get_logger("app.startup")
    logger.info(
        "Logging initialized", level=log_level, format=log_format, file=log_file or "console-only"
    )
