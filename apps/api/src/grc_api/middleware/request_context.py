"""Request-correlation middleware.

For every request it (1) resolves or generates a correlation id (honouring an inbound
``X-Request-Id`` / ``traceparent`` so traces span services), (2) binds the request context for
logging and audit, (3) times the request, and (4) emits one structured completion log line and
echoes ``X-Request-Id`` back to the caller. It deliberately contains no business logic
(Handbook §8.112: the edge authenticates/observes; it does not decide).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..observability import (
    RequestContext,
    bind_request_context,
    get_logger,
    reset_request_context,
)

_logger = get_logger("grc_api.request")

_REQUEST_ID_HEADER = b"x-request-id"
_TRACEPARENT_HEADER = b"traceparent"


def _header(scope: Scope, name: bytes) -> str | None:
    headers: Iterable[tuple[bytes, bytes]] = scope.get("headers", [])
    for key, value in headers:
        if key == name:
            return value.decode("latin-1")
    return None


def _trace_id_from_traceparent(traceparent: str | None) -> str | None:
    # W3C traceparent: version-traceid-spanid-flags
    if not traceparent:
        return None
    parts = traceparent.split("-")
    return parts[1] if len(parts) >= 2 and parts[1] else None


class RequestContextMiddleware:
    """Pure-ASGI middleware so correlation is bound before routing and survives streaming."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = _header(scope, _REQUEST_ID_HEADER) or uuid.uuid4().hex
        trace_id = _trace_id_from_traceparent(_header(scope, _TRACEPARENT_HEADER)) or request_id
        context = RequestContext(
            request_id=request_id,
            trace_id=trace_id,
            method=scope.get("method", ""),
            path=scope.get("path", ""),
        )
        token = bind_request_context(context)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode("latin-1")))
            await send(message)

        try:
            await self._app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            _logger.info(
                "request_completed",
                extra={
                    "http_method": context.method,
                    "http_path": context.path,
                    "http_status": status_code,
                    "duration_ms": elapsed_ms,
                },
            )
            reset_request_context(token)
