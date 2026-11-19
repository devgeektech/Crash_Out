"""
Centralized structured logging framework for Crash Out.

Supports:
- Console handler with formatted timestamps and log levels
- Rotating file logging under outputs/logs/app.log and outputs/logs/requests.log
- Structured JSON or colored stream output
- Request correlation ID tracking via ASGI Middleware
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import time
import uuid
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.paths import OUTPUT_DIR

LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
APP_LOG_PATH = os.path.join(LOGS_DIR, "app.log")
ACCESS_LOG_PATH = os.path.join(LOGS_DIR, "access.log")

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Initialize root and application loggers with console + rotating file handlers."""
    global _configured
    if _configured:
        return

    os.makedirs(LOGS_DIR, exist_ok=True)

    log_format = "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers on reloads
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    # Console Handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # App File Handler (Rotating 10MB x 5 backups)
    app_file_handler = logging.handlers.RotatingFileHandler(
        APP_LOG_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_file_handler.setLevel(level)
    app_file_handler.setFormatter(formatter)
    root_logger.addHandler(app_file_handler)

    # Access File Handler for HTTP requests
    access_logger = logging.getLogger("app.access")
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False  # Keep separate or log to access.log
    access_file_handler = logging.handlers.RotatingFileHandler(
        ACCESS_LOG_PATH,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    access_file_handler.setFormatter(formatter)
    access_logger.addHandler(access_file_handler)
    # Also attach console to access logger for development visibility
    access_logger.addHandler(console_handler)

    _configured = True
    logging.getLogger("app.logging").info("Logging framework initialized. Logs path: %s", LOGS_DIR)


def get_logger(name: str) -> logging.Logger:
    """Utility to get namespaced loggers."""
    return logging.getLogger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming HTTP requests, response status, duration, and correlation IDs."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        url_path = request.url.path

        # Process request
        try:
            response: Response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000.0
            status_code = response.status_code

            # Attach correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id

            # Only log detailed info for non-static or API/page routes
            if not url_path.startswith("/static/"):
                access_logger = logging.getLogger("app.access")
                access_logger.info(
                    "[%s] %s %s -> %d (%0.2fms) [client: %s]",
                    correlation_id[:8],
                    method,
                    url_path,
                    status_code,
                    duration_ms,
                    client_ip,
                )
            return response
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000.0
            logging.getLogger("app.access").exception(
                "[%s] %s %s -> FAILED (%0.2fms) [client: %s]: %s",
                correlation_id[:8],
                method,
                url_path,
                duration_ms,
                client_ip,
                exc,
            )
            raise
