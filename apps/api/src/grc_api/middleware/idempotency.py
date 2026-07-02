"""Idempotency middleware — retry-safety for consequential requests (Handbook §8.116).

A client may safely retry a mutating request by sending a stable ``Idempotency-Key`` header: the
first response is captured and replayed for any subsequent request carrying the same key, so a
duplicate never causes a duplicate business effect. The cache is scoped per credential + method +
path so keys cannot collide or leak across tenants, and is bounded (LRU).

This is a pure-ASGI, process-local reference implementation suitable for the single-process
in-memory binding; a multi-replica production deployment swaps the backing store for a shared one
(Redis) behind the same behaviour. Server errors (5xx) are never cached, so a failed call remains
retryable.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_IDEMPOTENCY_HEADER = b"idempotency-key"
_AUTHORIZATION_HEADER = b"authorization"


@dataclass
class _StoredResponse:
    status: int
    headers: list[tuple[bytes, bytes]]
    body: bytes


class IdempotencyMiddleware:
    def __init__(self, app: ASGIApp, *, max_entries: int = 2048) -> None:
        self._app = app
        self._max_entries = max_entries
        self._store: OrderedDict[str, _StoredResponse] = OrderedDict()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "") not in _MUTATING_METHODS:
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        idempotency_key = headers.get(_IDEMPOTENCY_HEADER)
        if not idempotency_key:
            await self._app(scope, receive, send)
            return

        cache_key = self._cache_key(scope, headers, idempotency_key)
        cached = self._store.get(cache_key)
        if cached is not None:
            self._store.move_to_end(cache_key)
            await self._replay(cached, send)
            return

        await self._capture_and_forward(cache_key, scope, receive, send)

    def _cache_key(self, scope: Scope, headers: dict[bytes, bytes], idempotency_key: bytes) -> str:
        # Scope by credential so keys never collide across principals/tenants. The credential is
        # hashed, never stored in the clear.
        credential = headers.get(_AUTHORIZATION_HEADER, b"")
        material = b"|".join(
            [
                hashlib.sha256(credential).digest(),
                scope.get("method", "").encode("latin-1"),
                scope.get("path", "").encode("latin-1"),
                idempotency_key,
            ]
        )
        return hashlib.sha256(material).hexdigest()

    async def _replay(self, stored: _StoredResponse, send: Send) -> None:
        headers = [*stored.headers, (b"idempotency-replayed", b"true")]
        await send({"type": "http.response.start", "status": stored.status, "headers": headers})
        await send({"type": "http.response.body", "body": stored.body, "more_body": False})

    async def _capture_and_forward(
        self, cache_key: str, scope: Scope, receive: Receive, send: Send
    ) -> None:
        status = 500
        response_headers: list[tuple[bytes, bytes]] = []
        body_chunks: list[bytes] = []

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_headers
            if message["type"] == "http.response.start":
                status = message["status"]
                response_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body_chunks.append(bytes(message.get("body", b"")))
            await send(message)

        await self._app(scope, receive, send_wrapper)

        # Cache only definitive (non-5xx) outcomes so failures stay retryable.
        if status < 500:
            self._put(cache_key, _StoredResponse(status, response_headers, b"".join(body_chunks)))

    def _put(self, cache_key: str, response: _StoredResponse) -> None:
        self._store[cache_key] = response
        self._store.move_to_end(cache_key)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)
