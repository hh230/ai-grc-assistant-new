"""Structured (JSON) logging with automatic request-correlation enrichment.

Logs are machine-parseable and every record emitted inside a request is tagged with the
request/trace id and (when known) the tenant + principal, so the interface→service chain is
traceable end to end (CLAUDE.md §6 #15, §19). No secrets or raw prompts are ever logged.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from .context import current_request_context

__all__ = ["configure_logging", "get_logger"]

_RESERVED = frozenset(
    logging.makeLogRecord({}).__dict__.keys() | {"message", "asctime", "taskName"}
)


class _JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON, enriched with request correlation fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        ctx = current_request_context()
        if ctx is not None:
            payload["request_id"] = ctx.request_id
            payload["trace_id"] = ctx.trace_id
            if ctx.organization_id:
                payload["organization_id"] = ctx.organization_id
            if ctx.user_id:
                payload["user_id"] = ctx.user_id
        # Promote structured extras passed via logger.info(..., extra={...}).
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    """Install a single stdout handler on the root logger. Idempotent per process."""
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Uvicorn's access logger is redundant with our request-completion log line.
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
