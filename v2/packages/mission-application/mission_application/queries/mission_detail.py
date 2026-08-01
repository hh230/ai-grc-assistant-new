"""`MissionDetailQuery` — the read-side service behind `GET /v1/missions/{id}` (CQRS read side).

It is the one place that composes the sources for the Mission Detail View: the frozen Core
(`MissionStorePort.get` — status/plan/findings/approval) and the read model (`get` — the product's
type/scope, ADR 0053), then maps them into a `MissionDetailView` that hides every implementation
detail (constraint 2). The HTTP route stays a thin adapter: resolve the tenant, call `execute`, 404
on `None`. As permissions, deliverable state, polling version, or caching arrive, they land here —
not the route (keeps `grc-api` a Composition Root + HTTP adapter, ADR 0052).

Entry point is `execute(...)` — the one convention every Query and Command in the project shares.
"""

from __future__ import annotations

from typing import Any

from mission_read_model import MissionListItem, MissionListReadModel
from pipeline_contracts import TenantContext

from mission_application.views import (
    ApprovalView,
    FindingView,
    MissionDetailView,
    PlanStepView,
)


class MissionDetailQuery:
    """Compose one mission's detail view, tenant-scoped fail-closed."""

    def __init__(self, store: Any, read_model: MissionListReadModel) -> None:
        self._store = store
        self._read_model = read_model

    def execute(self, mission_id: str, tenant: TenantContext) -> MissionDetailView | None:
        # The Core store is the source of truth for existence and is tenant-scoped: a missing or
        # cross-tenant mission is `None` → the caller turns that into a 404 (fail-closed).
        mission = self._store.get(mission_id, tenant)
        if mission is None:
            return None
        item = self._read_model.get(mission_id, tenant)
        return _to_view(mission, item)


def _to_view(mission: Any, item: MissionListItem | None) -> MissionDetailView:
    steps = list(mission.plan.steps) if mission.plan is not None else []
    descriptions = {step.id: step.description for step in steps}
    plan = tuple(PlanStepView(id=step.id, description=step.description) for step in steps)
    findings = tuple(
        FindingView(
            step_id=result.step_id,
            # A human-readable title: the plan step's description, not the raw step id.
            title=descriptions.get(result.step_id) or _humanize(result.step_id),
            summary=result.output,
            citations=tuple(result.citations),
            confidence=result.confidence,
        )
        for result in mission.step_results
    )
    return MissionDetailView(
        id=mission.id,
        type=item.mission_type if item else "",
        scope=item.title if item else "",
        status=mission.status.value,
        plan=plan,
        findings=findings,
        approval=_approval_view(mission.approval),
        created_at=mission.created_at,
        updated_at=mission.updated_at,
    )


def _approval_view(approval: Any) -> ApprovalView | None:
    if approval is None:
        return None
    if approval.is_pending:
        status = "pending"
    else:
        status = "approved" if approval.decision and approval.decision.approved else "rejected"
    return ApprovalView(id=approval.id, proposed_action=approval.reason, status=status)


def _humanize(step_id: str) -> str:
    return step_id.replace("_", " ").replace("-", " ").strip().capitalize()
