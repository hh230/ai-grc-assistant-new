"""`ApprovalQueueProjection` — the read side of "What decisions are waiting for me?" (Slice S6).

The one big new read component of the Product-Expansion phase — and it exists for exactly one
reason: **`mission-read-model` cannot answer this business question.** The read model knows *which*
missions are awaiting approval, but a *decision* needs the proposed action, how long it has waited,
its evidence, and the reference to act on — all of which live on the Core Mission's `approval`
(ADR 0044), in the Store.

So the projection is **read-only and computed on read** (like S5's Dashboard Projection): it
**composes** the reused `mission-read-model` (to *find* waiting missions) with the reused Mission
Store (to *detail* each). It stores nothing, holds no projector, and never mutates a mission —
Approve/Reject stay the S2 command. Materialize into a stored projection only if performance later
demands it.

Everything is tenant-scoped and fail-closed: the read model scopes the find, the store scopes each
load.
"""

from __future__ import annotations

from typing import Any

from mission_read_model import MissionListItem, MissionListReadModel
from pipeline_contracts import TenantContext

from mission_application.decision_views import DecisionItemView, RecentDecisionView

STATUS_AWAITING = "awaiting_approval"
# A decided approval leaves the mission COMPLETED (approved → resumed to the end) or CANCELLED
# (rejected → stopped fail-safe). Those are the two statuses a recent decision can be found under.
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
# Bounded: a person's waiting decisions, not an unbounded scan.
SCAN_LIMIT = 200
# Recent decided decisions to surface when nothing is waiting (keeps the page alive).
RECENT_DECISIONS = 2
DECIDED_SCAN_LIMIT = 50


def _proposed_action(reason: str) -> str:
    """The human proposed action out of the Core reason. The engine writes
    `"approval required before step <id>: <description>"`; the person cares about the *description*.
    Falls back to the whole reason if the shape ever differs."""
    _, sep, tail = reason.partition(": ")
    return tail.strip() if sep and tail.strip() else reason


def _evidence_count(mission: Any) -> int:
    """Distinct evidence (citations) gathered across the mission so far — the base behind the
    decision. Mirrors the Result's evidence count; never exposes the citation ids themselves."""
    return len({citation for result in mission.step_results for citation in result.citations})


class ApprovalQueueProjection:
    """Compose the tenant's waiting decisions from the read model + the store. Entry point:
    `execute`."""

    def __init__(self, store: Any, read_model: MissionListReadModel) -> None:
        self._store = store
        self._read_model = read_model

    def execute(self, tenant: TenantContext) -> tuple[DecisionItemView, ...]:
        page = self._read_model.list_missions(
            tenant, status=STATUS_AWAITING, page=1, page_size=SCAN_LIMIT
        )
        items: list[DecisionItemView] = []
        for row in page.items:
            mission = self._store.get(row.mission_id, tenant)
            # Fail-safe: the snapshot said awaiting, but only the live aggregate is the truth.
            if mission is None or not mission.has_active_approval:
                continue
            approval = mission.approval
            items.append(
                DecisionItemView(
                    mission_id=mission.id,
                    decision_id=approval.id,
                    proposed_action=_proposed_action(approval.reason),
                    mission_type=row.mission_type,
                    mission_scope=row.title,
                    waiting_since=approval.requested_at,
                    evidence_count=_evidence_count(mission),
                )
            )
        # Longest-waiting first — the decision that has waited most is the most urgent to make
        # (the page asks "what has waited longest for me?", not "what is newest?").
        items.sort(key=lambda item: (item.waiting_since, item.decision_id))
        return tuple(items)

    def recent_decisions(
        self, tenant: TenantContext, *, limit: int = RECENT_DECISIONS
    ) -> tuple[RecentDecisionView, ...]:
        """The last few decisions *already made* — shown when nothing is waiting so the page stays
        alive. A decided approval leaves the mission completed or cancelled, so we scan those, keep
        the ones whose approval carries a decision, most recently decided first. Read-only; no new
        command — Product Expansion adds a question, not a behaviour."""
        rows: list[MissionListItem] = []
        for status in (STATUS_COMPLETED, STATUS_CANCELLED):
            page = self._read_model.list_missions(
                tenant, status=status, page=1, page_size=DECIDED_SCAN_LIMIT
            )
            rows.extend(page.items)
        decisions: list[RecentDecisionView] = []
        for row in rows:
            mission = self._store.get(row.mission_id, tenant)
            if mission is None:
                continue
            approval = mission.approval
            if approval is None or approval.is_pending or approval.decision is None:
                continue
            decisions.append(
                RecentDecisionView(
                    proposed_action=_proposed_action(approval.reason),
                    approved=approval.decision.approved,
                    decided_at=approval.decision.decided_at,
                )
            )
        decisions.sort(key=lambda decision: decision.decided_at, reverse=True)
        return tuple(decisions[:limit])
