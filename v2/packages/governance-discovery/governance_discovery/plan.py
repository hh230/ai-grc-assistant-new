"""`GovernancePlan` / `PlanItem` — the persisted aggregates a `governance_plans`/
`governance_plan_items` row round-trips (ADR 0066 §3, §3.1, §5). Pure data, mirroring
`DiscoverySession`'s discipline exactly: no clock, no I/O, no database. Timestamps are always
caller-supplied. Constructing/synthesizing a plan from an `Applicability` result plus LLM-drafted
prose is Mission-side logic (the `PLAN_SYNTHESIS_TOOL`) — this module only owns the shape and the
few state transitions (`marked_done`, `reopened`, `with_evidence`) that Plan Execution needs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

PlanItemStatus = Literal["not_started", "in_progress", "done", "deferred", "not_applicable"]
PlanStatus = Literal["active", "superseded"]


@dataclass(frozen=True)
class PlanItem:
    id: str
    plan_id: str
    tenant_id: str
    pillar: str
    title: str
    objective: str
    expected_outcome: str
    rationale: str
    timeframe_bucket: str
    priority: str
    effort_size: str
    depends_on_item_ids: tuple[str, ...]
    status: PlanItemStatus
    source_signal_keys: tuple[str, ...]
    source_framework_refs: tuple[dict, ...]
    created_at: float
    updated_at: float
    due_at: float | None = None
    completed_at: float | None = None
    # What completing this item is equivalent to in the Signal vocabulary (ADR 0066 §5.3) — pinned
    # from the pack's `plan_seed.resolves_signal` at creation time. `None` for items too broad to
    # collapse into one signal (completing them only changes `status`).
    resolves_signal: dict | None = None
    # Always optional (ADR 0066 §5.4) — never a gate on `marked_done`.
    evidence_ids: tuple[str, ...] = ()
    confidence: float | None = None
    risk_if_skipped: str | None = None
    revisit_at: float | None = None

    @property
    def is_evidence_backed(self) -> bool:
        return len(self.evidence_ids) > 0

    def marked_in_progress(self, now: float) -> PlanItem:
        """Not started -> in progress (Phase 4): a practitioner has picked this up but not
        finished it yet. `PlanItemStatus` already named this state; nothing used it until now."""
        return replace(self, status="in_progress", updated_at=now)

    def marked_done(self, now: float) -> PlanItem:
        return replace(self, status="done", completed_at=now, updated_at=now)

    def reopened(self, now: float) -> PlanItem:
        """Un-completing needs no undo logic beyond this (ADR 0066 §5.3) — the item simply stops
        appearing in the 'currently done' set the next time `effective_signals()` is computed."""
        return replace(self, status="not_started", completed_at=None, updated_at=now)

    def with_evidence(self, evidence_ids: tuple[str, ...], now: float) -> PlanItem:
        return replace(self, evidence_ids=evidence_ids, updated_at=now)


@dataclass(frozen=True)
class GovernancePlan:
    id: str
    tenant_id: str
    source_mission_id: str
    status: PlanStatus
    version: int
    inferred_frameworks: tuple[dict, ...]
    maturity_baseline: dict  # {dimension: {"score", "stars", "label"}} — frozen at creation
    created_at: float
    updated_at: float
    source_session_id: str | None = None
    previous_plan_id: str | None = None
    maturity_at_supersession: dict | None = None
    executive_summary: str | None = None
    top_risks: tuple[dict, ...] = ()

    def superseded_by_next_version(self, current_maturity: dict, now: float) -> GovernancePlan:
        """Called on the OLD plan when a new one is approved (ADR 0066 §3.1) — never edits the
        plan's substantive content, only records the status transition and the live maturity this
        version actually reached."""
        return replace(
            self, status="superseded", maturity_at_supersession=current_maturity, updated_at=now
        )


@dataclass(frozen=True)
class PlanEvent:
    """One append-only audit fact about a `PlanItem` — `completed`/`reopened`/`evidence_attached`
    (ADR 0066 §5.3/§5.5). `sequence` is a database-assigned, monotonically increasing tie-breaker
    (Phase 3 hardening): `created_at` alone cannot deterministically order two events sharing a
    timestamp, and the ordering an audit trail relies on cannot depend on wall-clock precision."""

    id: str
    sequence: int
    plan_item_id: str
    tenant_id: str
    event_type: str
    actor_id: str
    created_at: float


__all__ = ["GovernancePlan", "PlanItem", "PlanItemStatus", "PlanStatus", "PlanEvent"]
