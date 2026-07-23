"""Human-approval value objects owned by the Mission aggregate (ADR 0044, Slice 1).

Approval is modelled as **two immutable value objects inside the Mission's consistency boundary** —
not a separate aggregate, not an entity with independent identity (ADR 0044 §1). The *request* is a
fact created when the mission pauses at a consequential step; the *decision* is a fact created only
when a human acts, so it is **absent until a decision exists**:

  * `ApprovalRequest`  — id, reason, requested_at, requested_by (+ the optional decision).
  * `ApprovalDecision` — approved, approver, comment, decided_at.

**Slice 1 scope:** the aggregate can *carry* a pending `ApprovalRequest` (its `decision` is always
`None` here) and round-trip it through the Mission Store. `approve()`/`reject()` (which *set* the
`ApprovalDecision`) and the `MissionApproved`/`MissionRejected` events are **Slice 2**, deliberately
not implemented here. These objects hold no user/role knowledge (RBAC lives above the pure
aggregate, ADR 0044 assumption 3): `requested_by`/`approver` are recorded as plain data, never
authorized here.

The objects are frozen dataclasses, consistent with `Plan`/`PlanStep`/`StepResult`, and reuse the
platform's one serialization convention (`pipeline_contracts.dataclass_dict`), which serializes the
nested `decision` (or `None`) automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline_contracts import dataclass_dict

from mission_engine.ids import new_approval_id


@dataclass(frozen=True)
class ApprovalDecision:
    """A human's resolution of an approval gate — the decision fact (ADR 0044 §1). `approved=True`
    is an approval, `approved=False` a rejection; `approver` is recorded as data (the aggregate does
    not authorize it). Not produced in Slice 1 — `approve()`/`reject()` create it in Slice 2."""

    approved: bool
    approver: str = ""
    comment: str = ""
    decided_at: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class ApprovalRequest:
    """A mission's request for human approval of a consequential step — the request fact (ADR 0044
    §1). Created by the engine's pause path; carries **why** the mission paused. `decision` is
    `None` while the request is *pending* and is set exactly once when a human decides (Slice 2). A
    rejection or approval produces a *new* `ApprovalRequest` carrying its `ApprovalDecision`, never
    a mutation, so "requested" and "decided" stay two distinct, append-only facts an audit needs."""

    reason: str = ""
    requested_by: str = ""
    requested_at: float = 0.0
    id: str = field(default_factory=new_approval_id)
    decision: ApprovalDecision | None = None

    @property
    def is_pending(self) -> bool:
        """Whether this request is still awaiting a decision (its `decision` is unset). An *active*
        request (ADR 0044's one-active-request invariant) is exactly a pending one."""
        return self.decision is None

    def to_dict(self) -> dict[str, object]:
        # `dataclass_dict` serializes the nested `decision` (or None) via `to_plain` automatically.
        return dataclass_dict(self)
