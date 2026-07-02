"""Request-scoped correlation context.

A :class:`RequestContext` is bound to a :class:`contextvars.ContextVar` at the start of every
request and read by the logger and audit paths. It carries the correlation/trace id plus the
tenant + principal (once authenticated) so logs and audit records can attribute every action
without threading parameters through every call.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, replace

__all__ = [
    "RequestContext",
    "bind_request_context",
    "current_request_context",
    "reset_request_context",
]


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    trace_id: str
    method: str
    path: str
    organization_id: str | None = None
    user_id: str | None = None

    def with_principal(self, *, organization_id: str, user_id: str) -> RequestContext:
        return replace(self, organization_id=organization_id, user_id=user_id)


_REQUEST_CONTEXT: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
    "grc_api_request_context", default=None
)


def bind_request_context(context: RequestContext) -> contextvars.Token[RequestContext | None]:
    """Bind the context for the current task; return a token to reset it afterwards."""
    return _REQUEST_CONTEXT.set(context)


def current_request_context() -> RequestContext | None:
    return _REQUEST_CONTEXT.get()


def reset_request_context(token: contextvars.Token[RequestContext | None]) -> None:
    _REQUEST_CONTEXT.reset(token)
