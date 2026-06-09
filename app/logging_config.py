"""
Logging configuration for InfusionFox.

Production logs are JSON-formatted lines on stdout, suitable for shipping
to Loki, CloudWatch, Datadog, etc. Development logs are human-readable
text. Selection is via the `INFUSIONFOX_LOG_FORMAT` env var:

    INFUSIONFOX_LOG_FORMAT=json   → JSON one-line-per-record
    INFUSIONFOX_LOG_FORMAT=text   → human-readable (default in dev)

Log level is via `INFUSIONFOX_LOG_LEVEL` (default INFO).

Usage from anywhere in the app:
    from app.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("calculator computed", extra={"slug": "norepi", "weight_kg": 5.0})

The `extra={}` dict is included as structured fields in JSON output.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# Standard LogRecord attributes that are NOT custom `extra` fields.
# When formatting JSON we copy everything else from the record's __dict__
# into the output, but skip these.
_STANDARD_ATTRS = {
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
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per log line, with extra fields preserved."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Surface custom keyword fields supplied via `extra={...}`.
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        # Format exception info if present.
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Set up the root logger. Call once at app startup."""
    level = os.environ.get("INFUSIONFOX_LOG_LEVEL", "INFO").upper()
    fmt = os.environ.get("INFUSIONFOX_LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root = logging.getLogger()
    # Replace existing handlers so re-config (e.g. in tests) is clean.
    root.handlers = [handler]
    root.setLevel(level)

    # Quiet down chatty third-party loggers
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("multipart").setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper so callers don't import logging directly."""
    return logging.getLogger(name)
