"""HTTP response shapes for the Missions View (REST_API_CONTRACT_V1 §2, §4).

Representations **hide implementation**: a row exposes the product's `type` and `scope`, the
`status`, and timestamps — never tool names, chunk ids, or the mission's internal `goal` text. The
list is paged so a large tenant never serializes unbounded.
"""

from __future__ import annotations

from document_read_model import DocumentItem
from mission_application import (
    DashboardView,
    DecisionItemView,
    MissionDetailView,
    RecentDecisionView,
)
from mission_read_model import MissionListItem, MissionPage
from pydantic import BaseModel


class DecisionBody(BaseModel):
    """Optional body for an approve/reject command — a reviewer's note."""

    comment: str = ""


class CreateMissionBody(BaseModel):
    """Start work: a Mission type (one of the 6), a scope, and optional documents (REST_API_CONTRACT
    §3). Product language in, `(goal, plan)` out — the create command maps it via the catalog."""

    type: str
    scope: str
    document_ids: list[str] = []


class MissionCreatedResponse(BaseModel):
    """The Mission Created **review station** payload: the mission (type · scope · status · plan) +
    a plan summary — `steps` to run and `human_approvals` (gates) it will need — so the user reviews
    *what they created* before *how it runs*. No auto-run; the user Starts it from here."""

    mission: MissionDetailView
    steps: int
    human_approvals: int


class MissionRow(BaseModel):
    """One Missions-View row."""

    id: str
    type: str
    scope: str
    status: str
    created_at: float
    updated_at: float

    @classmethod
    def from_item(cls, item: MissionListItem) -> MissionRow:
        # `title` in the read model is the human-readable scope/subject the row shows.
        return cls(
            id=item.mission_id,
            type=item.mission_type,
            scope=item.title,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class MissionListResponse(BaseModel):
    """A page of the tenant's missions plus the paging facts the UI renders controls from."""

    items: list[MissionRow]
    page: int
    page_size: int
    total: int
    has_next: bool

    @classmethod
    def from_page(cls, page: MissionPage) -> MissionListResponse:
        return cls(
            items=[MissionRow.from_item(item) for item in page.items],
            page=page.page,
            page_size=page.page_size,
            total=page.total,
            has_next=page.has_next,
        )


class DocumentRow(BaseModel):
    """One document in the Knowledge view (REST_API_CONTRACT_V1 §2 `Document`). Carries the
    product's `evidence_kind` (its Evidence Collection) and its ingestion `status` — never a chunk
    id, an embedding, or any pgvector detail (Knowledge = Evidence, not a File Manager)."""

    id: str
    filename: str
    evidence_kind: str
    status: str
    uploaded_at: float
    size: int

    @classmethod
    def from_item(cls, item: DocumentItem) -> DocumentRow:
        return cls(
            id=item.document_id,
            filename=item.filename,
            evidence_kind=item.evidence_kind,
            status=item.status,
            uploaded_at=item.uploaded_at,
            size=item.size,
        )


class DocumentListResponse(BaseModel):
    """The tenant's documents. The Knowledge view groups these into Evidence Collections by
    `evidence_kind` client-side — grouping is presentation, so there is no `GET /collections`."""

    items: list[DocumentRow]

    @classmethod
    def from_items(cls, items: tuple[DocumentItem, ...]) -> DocumentListResponse:
        return cls(items=[DocumentRow.from_item(item) for item in items])


class DecisionRow(BaseModel):
    """One waiting **decision** on the Decisions view (§4 Approvals queue item). The unit is a
    decision, not a mission: `proposed_action` is what to decide; `mission_*` are context;
    `waiting_since` is when it started; `decision_id` is what Approve/Reject acts on. No step ids,
    tool names, or pipeline internals."""

    mission_id: str
    decision_id: str
    proposed_action: str
    mission_type: str
    mission_scope: str
    waiting_since: float
    evidence_count: int

    @classmethod
    def from_item(cls, item: DecisionItemView) -> DecisionRow:
        return cls(
            mission_id=item.mission_id,
            decision_id=item.decision_id,
            proposed_action=item.proposed_action,
            mission_type=item.mission_type,
            mission_scope=item.mission_scope,
            waiting_since=item.waiting_since,
            evidence_count=item.evidence_count,
        )


class DecisionsResponse(BaseModel):
    """The tenant's waiting decisions (longest-waiting first). The Decisions view renders each as a
    Decision card; Approve/Reject reuse the existing mission approval command."""

    items: list[DecisionRow]

    @classmethod
    def from_items(cls, items: tuple[DecisionItemView, ...]) -> DecisionsResponse:
        return cls(items=[DecisionRow.from_item(item) for item in items])


class RecentDecisionRow(BaseModel):
    """A decision already made — shown when nothing is waiting so the page stays alive. `approved`
    distinguishes an approval from a rejection; no mission internals."""

    proposed_action: str
    approved: bool
    decided_at: float

    @classmethod
    def from_item(cls, item: RecentDecisionView) -> RecentDecisionRow:
        return cls(
            proposed_action=item.proposed_action,
            approved=item.approved,
            decided_at=item.decided_at,
        )


class RecentDecisionsResponse(BaseModel):
    """The last few decisions already made (most recently decided first)."""

    items: list[RecentDecisionRow]

    @classmethod
    def from_items(cls, items: tuple[RecentDecisionView, ...]) -> RecentDecisionsResponse:
        return cls(items=[RecentDecisionRow.from_item(item) for item in items])


class RecentMissionRow(BaseModel):
    """One recently-completed mission on the Dashboard (a link to its Work Surface)."""

    id: str
    type: str
    scope: str
    completed_at: float


class CoverageSnapshot(BaseModel):
    """The Coverage **Snapshot** — a point-in-time picture from the latest completed Gap Assessments
    (`percent` is 0–1). Not a compliance score (Dashboard ≠ Analytics)."""

    percent: float
    covered: int
    total: int
    assessments: int


class DashboardResponse(BaseModel):
    """"System state now" for the tenant (REST_API_CONTRACT_V1 §4). Attention counts first, coverage
    last; `coverage` is null until a Gap Assessment has completed. No tool/pipeline internals."""

    waiting: int
    running: int
    failed: int
    recent: list[RecentMissionRow]
    coverage: CoverageSnapshot | None

    @classmethod
    def from_view(cls, view: DashboardView) -> DashboardResponse:
        coverage = (
            CoverageSnapshot(
                percent=view.coverage.percent,
                covered=view.coverage.covered,
                total=view.coverage.total,
                assessments=view.coverage.assessments,
            )
            if view.coverage is not None
            else None
        )
        return cls(
            waiting=view.waiting,
            running=view.running,
            failed=view.failed,
            recent=[
                RecentMissionRow(
                    id=item.mission_id,
                    type=item.mission_type,
                    scope=item.title,
                    completed_at=item.completed_at,
                )
                for item in view.recent
            ],
            coverage=coverage,
        )
