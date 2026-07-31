"""The Approval Service — all approval *logic* over the aggregate + a swappable Store.

Behaviour lives here (create / approve / reject / cancel / expire); the Store only persists. So a
different Store (JSON, SQLite, Postgres) needs no logic change. Every mutation goes through the
aggregate's guarded transitions — the Service never sets a status directly. It injects a clock + id
factory so tests are deterministic.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from devteam_approval.approval import (
    Actor,
    ApprovalDecision,
    ApprovalError,
    ApprovalOutcome,
    ApprovalPolicy,
    ApprovalRequest,
)
from devteam_approval.store import ApprovalStore, InMemoryApprovalStore


class ApprovalService:
    """Opens and decides approval requests over a Store."""

    def __init__(
        self,
        store: ApprovalStore | None = None,
        *,
        clock: Callable[[], float] = time.time,
        new_id: Callable[[], str] | None = None,
    ) -> None:
        self._store: ApprovalStore = store if store is not None else InMemoryApprovalStore()
        self._clock = clock
        self._new_id = new_id if new_id is not None else (lambda: uuid.uuid4().hex)

    # --- open ---

    def create(
        self,
        *,
        target_ref: str,
        resume_token: str,
        policy: ApprovalPolicy,
        expires_at: float = 0.0,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            id=f"apr_{self._new_id()}",
            target_ref=target_ref,
            resume_token=resume_token,
            policy=policy,
            expires_at=expires_at,
            created_at=self._clock(),
        )
        self._store.save(request)
        return request

    # --- decide (records a decision event on the request) ---

    def approve(self, request_id: str, *, actor: Actor, comment: str = "") -> ApprovalRequest:
        return self._decide(request_id, ApprovalOutcome.GRANTED, actor, comment)

    def reject(self, request_id: str, *, actor: Actor, comment: str = "") -> ApprovalRequest:
        return self._decide(request_id, ApprovalOutcome.REJECTED, actor, comment)

    def _decide(
        self, request_id: str, outcome: ApprovalOutcome, actor: Actor, comment: str
    ) -> ApprovalRequest:
        request = self._require(request_id)
        decision = ApprovalDecision(
            id=f"dec_{self._new_id()}",
            outcome=outcome,
            actor=actor,
            comment=comment,
            at=self._clock(),
        )
        return self._save(request.decide(decision))

    # --- cancel / expire (a status, not a decision) ---

    def cancel(self, request_id: str) -> ApprovalRequest:
        return self._save(self._require(request_id).cancel())

    def cancel_for_target(self, target_ref: str) -> ApprovalRequest | None:
        """Cancel the pending request for a target that closed / was replaced — no hanging gate."""
        request = self.pending_for_target(target_ref)
        return self.cancel(request.id) if request is not None else None

    def expire_due(self) -> list[ApprovalRequest]:
        """Expire every pending request past its deadline (called from the tick); returns them."""
        now = self._clock()
        return [self._save(r.expire()) for r in self.pending() if r.is_expired(now)]

    # --- queries ---

    def get(self, request_id: str) -> ApprovalRequest | None:
        return self._store.load(request_id)

    def pending(self) -> tuple[ApprovalRequest, ...]:
        return tuple(r for r in self._store.list() if r.is_pending)

    def pending_for_target(self, target_ref: str) -> ApprovalRequest | None:
        return next(
            (r for r in self._store.list() if r.is_pending and r.target_ref == target_ref),
            None,
        )

    def for_target(self, target_ref: str) -> ApprovalRequest | None:
        """The request gating a target, any status. At most one is live per target because the host
        clears it on close (so a recurrence opens a fresh gate)."""
        return next((r for r in self._store.list() if r.target_ref == target_ref), None)

    def all(self) -> tuple[ApprovalRequest, ...]:
        return self._store.list()

    def clear_target(self, target_ref: str) -> None:
        """Remove every request for a target — called when its problem closes, so the next episode
        of the same problem opens a fresh gate rather than reusing a stale decision."""
        for request in [r for r in self._store.list() if r.target_ref == target_ref]:
            self._store.delete(request.id)

    # --- internals ---

    def _save(self, request: ApprovalRequest) -> ApprovalRequest:
        self._store.save(request)
        return request

    def _require(self, request_id: str) -> ApprovalRequest:
        request = self._store.load(request_id)
        if request is None:
            raise ApprovalError(f"no approval request {request_id!r}")
        return request
