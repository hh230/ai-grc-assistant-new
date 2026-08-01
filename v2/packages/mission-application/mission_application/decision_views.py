"""The **Decisions** View Model (Slice S6) — "What decisions are waiting for me?".

A framework-agnostic dataclass: one **decision** waiting for the caller, across all their missions.
The unit is a *decision*, not a mission (the mission is only context). It carries the minimum a
person needs to decide in five seconds — the proposed action, its mission, how long it has waited,
and how much evidence stands behind it — and no implementation detail (no step ids as such, no
tools, no pipeline). `decision_id` is the opaque reference Approve/Reject acts on (the same the Work
Surface already uses). The product word is **Decisions**; the internal projection is the
`ApprovalQueueProjection`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionItemView:
    """One waiting decision. `proposed_action` is what the human is deciding on; the mission fields
    are context; `waiting_since` is when it started waiting; `evidence_count` is the distinct
    evidence gathered so far. `decision_id` is the reference Approve/Reject acts on."""

    mission_id: str
    decision_id: str
    proposed_action: str
    mission_type: str
    mission_scope: str
    waiting_since: float
    evidence_count: int


@dataclass(frozen=True)
class RecentDecisionView:
    """A decision already made — shown when nothing is waiting, so the page stays alive (like the
    Dashboard). `approved=True` is an approval, `False` a rejection; `decided_at` orders them."""

    proposed_action: str
    approved: bool
    decided_at: float
