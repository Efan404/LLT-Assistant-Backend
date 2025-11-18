"""Structured logging configuration for LLT Assistant Backend."""

import json
import logging
import logging.config
import sys
from typing import Any, Dict

from app.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id

        if hasattr(record, "event"):
            log_entry["event"] = record.event

        if hasattr(record, "file_path"):
            log_entry["file_path"] = record.file_path

        if hasattr(record, "analysis_id"):
            log_entry["analysis_id"] = record.analysis_id

        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        if hasattr(record, "error_type"):
            log_entry["error_type"] = record.error_type

        if hasattr(record, "stack_trace"):
            log_entry["stack_trace"] = record.stack_trace

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Custom text formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text."""
        # Add correlation ID if present
        correlation_id = getattr(record, "correlation_id", "")
        if correlation_id:
            record.correlation_id_str = f"[{correlation_id}] "
        else:
            record.correlation_id_str = ""

        return super().format(record)


def setup_logging() -> None:
    """Set up logging configuration."""

    # Define formatters
    json_formatter = JSONFormatter()
    text_formatter = TextFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(correlation_id_str)s%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Define handlers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))

    if settings.log_format == "json":
        console_handler.setFormatter(json_formatter)
    else:
        console_handler.setFormatter(text_formatter)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        handlers=[console_handler],
        force=True,
    )

    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Set up request logging
    setup_request_logging()


def setup_request_logging() -> None:
    """Set up request/response logging middleware."""

    class RequestLoggingMiddleware:
        """Middleware for logging HTTP requests and responses."""

        def __init__(self, app):
            self.app = app
            self.logger = logging.getLogger("llt.request")

        async def __call__(self, scope, receive, send):
            """Process request and log details."""
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            import time
            from uuid import uuid4

            correlation_id = str(uuid4())
            start_time = time.time()

            # Log request
            method = scope["method"]
            path = scope["path"]

            self.logger.info(
                "Request started",
                extra={
                    "correlation_id": correlation_id,
                    "event": "request_started",
                    "method": method,
                    "path": path,
                    "query_string": scope.get("query_string", b"").decode(),
                },
            )

            # Wrap send to capture response
            async def wrapped_send(message):
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    duration_ms = int((time.time() - start_time) * 1000)

                    self.logger.info(
                        "Request completed",
                        extra={
                            "correlation_id": correlation_id,
                            "event": "request_completed",
                            "method": method,
                            "path": path,
                            "status_code": status_code,
                            "duration_ms": duration_ms,
                        },
                    )

                await send(message)

            try:
                await self.app(scope, receive, wrapped_send)
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)

                self.logger.error(
                    "Request failed",
                    extra={
                        "correlation_id": correlation_id,
                        "event": "request_failed",
                        "method": method,
                        "path": path,
                        "duration_ms": duration_ms,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

                raise


def log_analysis_request(correlation_id: str, file_count: int, mode: str) -> None:
    """Log analysis request details."""
    logger = logging.getLogger("llt.analysis")
    logger.info(
        "Analysis request received",
        extra={
            "correlation_id": correlation_id,
            "event": "analysis_request",
            "file_count": file_count,
            "mode": mode,
        },
    )


def log_analysis_complete(
    correlation_id: str, issues_found: int, duration_ms: int
) -> None:
    """Log analysis completion details."""
    logger = logging.getLogger("llt.analysis")
    logger.info(
        "Analysis completed",
        extra={
            "correlation_id": correlation_id,
            "event": "analysis_complete",
            "issues_found": issues_found,
            "duration_ms": duration_ms,
        },
    )


def log_analysis_error(correlation_id: str, error: Exception) -> None:
    """Log analysis error details."""
    logger = logging.getLogger("llt.analysis")
    logger.error(
        "Analysis failed",
        extra={
            "correlation_id": correlation_id,
            "event": "analysis_error",
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
        exc_info=True,
    )


def log_llm_request(correlation_id: str, model: str, message_count: int) -> None:
    """Log LLM API request details."""
    logger = logging.getLogger("llt.llm")
    logger.info(
        "LLM request sent",
        extra={
            "correlation_id": correlation_id,
            "event": "llm_request",
            "model": model,
            "message_count": message_count,
        },
    )


def log_llm_response(
    correlation_id: str, response_length: int, duration_ms: int
) -> None:
    """Log LLM API response details."""
    logger = logging.getLogger("llt.llm")
    logger.info(
        "LLM response received",
        extra={
            "correlation_id": correlation_id,
            "event": "llm_response",
            "response_length": response_length,
            "duration_ms": duration_ms,
        },
    )


def log_llm_error(correlation_id: str, error: Exception, retry_count: int) -> None:
    """Log LLM API error details."""
    logger = logging.getLogger("llt.llm")
    logger.error(
        "LLM request failed",
        extra={
            "correlation_id": correlation_id,
            "event": "llm_error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "retry_count": retry_count,
        },
    )
