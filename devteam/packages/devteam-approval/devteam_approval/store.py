"""Persistence for approval requests — save / load / list / delete only, no logic.

The Store is a pure repository so it can be swapped (in-memory now; JSON, SQLite, Postgres later)
without moving any approval logic with it — that all lives in ``ApprovalService``. The Store never
runs a transition, holds a clock, or mints an id.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from devteam_approval.approval import ApprovalRequest


@runtime_checkable
class ApprovalStore(Protocol):
    """A repository of approval requests, keyed by id. Persistence only."""

    def save(self, request: ApprovalRequest) -> None: ...

    def load(self, request_id: str) -> ApprovalRequest | None: ...

    def list(self) -> tuple[ApprovalRequest, ...]: ...

    def delete(self, request_id: str) -> None: ...


class InMemoryApprovalStore:
    """A dict-backed store. Swap for a durable realization without touching ``ApprovalService``."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def save(self, request: ApprovalRequest) -> None:
        self._requests[request.id] = request

    def load(self, request_id: str) -> ApprovalRequest | None:
        return self._requests.get(request_id)

    def list(self) -> tuple[ApprovalRequest, ...]:
        return tuple(self._requests.values())

    def delete(self, request_id: str) -> None:
        self._requests.pop(request_id, None)
