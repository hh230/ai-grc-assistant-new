"""The Approval Domain — a generic, resumable approval model (S5, on the frozen Core).

An ``ApprovalRequest`` gates a **resumable target** (a problem, a mission, a workflow, a deployment,
a risk acceptance, a policy publication — anything), not bound to one domain. It carries a Policy
(authority level + required role + why), a Status, an expiry, and a ``resume_token`` — the opaque
handle the target uses to continue once a decision lands. The **decision is a separate object** (its
own id, actor, comment, timestamp), so a request can gain delegation, proxy approval, re-open, or
multi-stage approvals later without changing its shape.

This package is pure and domain-neutral: it produces approval *state*, not lifecycle events. An
adapter in the consuming system turns a decided request into whatever event that system understands
(for the Mission Lifecycle, a generic ApprovalGranted/ApprovalRejected → Coordinator.notify). The
Core stays frozen; the Approval Domain never imports it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from enum import Enum


class ApprovalStatus(str, Enum):
    """A request's lifecycle. Only PENDING moves; the rest are terminal (never left hanging)."""

    PENDING = "pending"  # awaiting a decision
    GRANTED = "granted"  # a human approved
    REJECTED = "rejected"  # a human rejected
    EXPIRED = "expired"  # the deadline passed with no decision
    CANCELLED = "cancelled"  # the target closed / was replaced / was admin-cancelled


class ApprovalOutcome(str, Enum):
    """A DECISION's outcome. Expiry and cancellation are statuses without a decision."""

    GRANTED = "granted"
    REJECTED = "rejected"


_TERMINAL = frozenset(
    {
        ApprovalStatus.GRANTED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.CANCELLED,
    }
)


class ApprovalError(Exception):
    """An illegal approval transition (e.g. deciding a request that is no longer pending)."""


@dataclass(frozen=True)
class ApprovalPolicy:
    """Why a decision is required + who may make it. ``requirement`` is a generic authority level —
    the consuming system maps its own policy in; ``required_role`` names who must decide ("" = any
    authorized human)."""

    requirement: str
    required_role: str = ""
    reason: str = ""


@dataclass(frozen=True)
class Actor:
    """Who made a decision — enough identity for a complete audit trail (``actor_id`` + a display
    ``name`` + a ``role``). Deliberately small: an SSO/OAuth identity maps onto this later without
    touching the Approval Domain."""

    actor_id: str
    name: str = ""
    role: str = ""


@dataclass(frozen=True)
class ApprovalDecision:
    """One decision on a request — its own entity, so a request can carry several over time
    (delegation, re-open, multi-stage) without changing shape. ``actor`` is who decided (full audit
    identity); ``at`` is when it was made."""

    outcome: ApprovalOutcome
    actor: Actor
    comment: str = ""
    at: float = 0.0
    id: str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex}")


@dataclass(frozen=True)
class ApprovalRequest:
    """A gate on a resumable target. Immutable: every transition returns a new request (the Core's
    value-object pattern). Decisions are event-sourced — ``decisions`` is an append-only log and
    ``current_decision`` derives from it — so delegation / proxy / multi-stage / re-review are added
    later by appending decisions, not by reshaping this. ``PENDING → GRANTED | REJECTED | EXPIRED |
    CANCELLED``; terminals do not move."""

    target_ref: str
    resume_token: str
    policy: ApprovalPolicy
    status: ApprovalStatus = ApprovalStatus.PENDING
    expires_at: float = 0.0  # 0.0 = never expires
    created_at: float = 0.0  # when the gate opened — a projection reads it as "waiting since"
    decisions: tuple[ApprovalDecision, ...] = ()  # the append-only decision event log
    id: str = field(default_factory=lambda: f"apr_{uuid.uuid4().hex}")

    @property
    def current_decision(self) -> ApprovalDecision | None:
        """The decision that produced the current state — the last event in the log."""
        return self.decisions[-1] if self.decisions else None

    @property
    def is_pending(self) -> bool:
        return self.status is ApprovalStatus.PENDING

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL

    def is_expired(self, now: float) -> bool:
        """Pending and past its (non-zero) deadline — the tick expires these so none hang."""
        return self.is_pending and self.expires_at > 0.0 and now >= self.expires_at

    def decide(self, decision: ApprovalDecision) -> ApprovalRequest:
        """Append a decision to the log and move to its outcome's status. One decision is terminal
        today; a future multi-stage policy would keep it PENDING until enough decisions accrue."""
        self._require_pending("decide")
        granted = decision.outcome is ApprovalOutcome.GRANTED
        status = ApprovalStatus.GRANTED if granted else ApprovalStatus.REJECTED
        return replace(self, status=status, decisions=(*self.decisions, decision))

    def expire(self) -> ApprovalRequest:
        self._require_pending("expire")
        return replace(self, status=ApprovalStatus.EXPIRED)

    def cancel(self) -> ApprovalRequest:
        self._require_pending("cancel")
        return replace(self, status=ApprovalStatus.CANCELLED)

    def _require_pending(self, action: str) -> None:
        if not self.is_pending:
            raise ApprovalError(f"cannot {action}: request {self.id} is {self.status.value}")
