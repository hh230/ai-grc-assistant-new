"""`ResultQuery` — the read-side service behind `GET /v1/missions/{id}/deliverable` (Slice S3).

It loads the mission (tenant-scoped, fail-closed), enforces that a Result exists **only when the
mission is Completed**, asks the registry for the right builder, then **assembles the page**: the
builder returns only the `ResultContent`; the query wraps it with the **frame** (Trust Bar, title,
metadata) into a `ResultView`. So each layer has one job — Builder: content · Query: page ·
Presenter: display. The route stays a thin adapter: `None`→404, `DeliverableNotReady`→409, else the
view. Entry point is `execute(...)`.
"""

from __future__ import annotations

from typing import Any

from pipeline_contracts import TenantContext

from mission_application.builders import DeliverableBuilderRegistry
from mission_application.contracts import DeliverableNotReady
from mission_application.result_views import ResultContent, ResultView, TrustBar


class ResultQuery:
    def __init__(
        self,
        store: Any,
        read_model: Any,
        registry: DeliverableBuilderRegistry,
    ) -> None:
        self._store = store
        self._read_model = read_model
        self._registry = registry

    def execute(self, mission_id: str, tenant: TenantContext) -> ResultView | None:
        # Existence is the Core's truth, tenant-scoped: absent or cross-tenant → None → 404.
        mission = self._store.get(mission_id, tenant)
        if mission is None:
            return None
        # Derived, not stored: the Result exists only once the mission has completed.
        if mission.status.value != "completed":
            raise DeliverableNotReady(mission_id)
        # Result adapts to the mission: the registry selects a builder (keyed on the mission type
        # from the read-model projection today; the whole mission is passed for future criteria).
        item = self._read_model.get(mission_id, tenant)
        mission_type = item.mission_type if item is not None else ""
        content = self._registry.for_mission(mission, mission_type).build_content(mission)
        # The query owns the frame: Trust Bar + title around the builder's content.
        return ResultView(
            mission_id=mission.id,
            title=mission.goal,
            trust=TrustBar(
                evidence_count=_evidence_count(content),
                human_review=_human_review(mission),
                updated_at=mission.updated_at,
            ),
            content=content,
        )


def _evidence_count(content: ResultContent) -> int:
    return len({citation for section in content.sections for citation in section.citations})


def _human_review(mission: Any) -> str:
    approval = mission.approval
    if approval is None:
        return "Not required"
    if approval.is_pending:
        return "Pending"
    return "Approved" if approval.decision and approval.decision.approved else "Rejected"
