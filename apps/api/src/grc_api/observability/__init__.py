"""Observability: structured logging and request-scoped correlation context.

Every request carries a correlation id (the trace id) that propagates from the HTTP edge
through the orchestrator → agent → tool → service chain (CLAUDE.md §6 #15), so any AI action
or state change is reconstructable for audit (CLAUDE.md §19).
"""

from __future__ import annotations

from .context import (
    RequestContext,
    bind_request_context,
    current_request_context,
    reset_request_context,
)
from .logging import configure_logging, get_logger

__all__ = [
    "RequestContext",
    "bind_request_context",
    "current_request_context",
    "reset_request_context",
    "configure_logging",
    "get_logger",
]
