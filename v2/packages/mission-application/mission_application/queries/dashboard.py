"""`DashboardProjection` — the read side of "What needs my attention right now?" (Slice S5).

**A read-only aggregation, computed on read.** There is no dashboard table, no projector, and no
persistence (design rule 4): the projection is a *query* that composes existing read models at read
time. It answers a genuinely new business question — the attention landing — so it earns its place
under guard 7; were it ever a performance problem it would *then* be a stored projection, never up
front.

It composes **two independent providers** (design rule 5), rather than computing everything inline:

    DashboardProjection
        ├── MissionSummaryProvider   — over the reused mission-read-model (S1)
        └── CoverageRollupProvider   — the Coverage Snapshot, its OWN capability (reused later by
                                       the Executive / Vendor / Compliance dashboards), over the
                                       reused ResultQuery (S3); a new type is an addition, not limb.

Everything is tenant-scoped and fail-closed by construction — the providers only read the caller's
tenant through the read model's own scoping.
"""

from __future__ import annotations

from mission_read_model import MissionListReadModel
from pipeline_contracts import TenantContext

from mission_application.contracts import DeliverableNotReady
from mission_application.dashboard_views import (
    CoverageSnapshotView,
    DashboardView,
    RecentMissionView,
)
from mission_application.queries.result import ResultQuery
from mission_application.result_views import GapAssessmentContent

# The mission-status snapshots the Dashboard groups by (values of the Core `MissionStatus`). Named,
# not magic, so the mapping "attention word → status" is explicit.
STATUS_WAITING = "awaiting_approval"
STATUS_RUNNING = "executing"
STATUS_FAILED = "failed"
STATUS_COMPLETED = "completed"

MISSION_TYPE_GAP = "gap_assessment"
RECENT_LIMIT = 5
# How many completed Gap Assessments the Coverage Snapshot rolls up (bounded — a snapshot, not scan)
COVERAGE_SCAN_LIMIT = 200


class MissionSummaryProvider:
    """The Dashboard's mission-attention read — a thin composition of the reused read model; owns no
    state. Each count is one tenant-scoped filtered read; the recent list, one more."""

    def __init__(self, read_model: MissionListReadModel) -> None:
        self._read_model = read_model

    def _count(self, tenant: TenantContext, status: str) -> int:
        # Reuse the read model's own filtered total (a COUNT at scale) — no new read-model method.
        return self._read_model.list_missions(tenant, status=status).total

    def summarize(
        self, tenant: TenantContext
    ) -> tuple[int, int, int, tuple[RecentMissionView, ...]]:
        waiting = self._count(tenant, STATUS_WAITING)
        running = self._count(tenant, STATUS_RUNNING)
        failed = self._count(tenant, STATUS_FAILED)
        page = self._read_model.list_missions(
            tenant, status=STATUS_COMPLETED, page=1, page_size=RECENT_LIMIT
        )
        recent = tuple(
            RecentMissionView(
                mission_id=item.mission_id,
                mission_type=item.mission_type,
                title=item.title,
                completed_at=item.updated_at,
            )
            for item in page.items
        )
        return waiting, running, failed, recent


class CoverageRollupProvider:
    """The **Coverage Snapshot** — an independent capability, not a limb of the Dashboard. It rolls
    up the tenant's completed Gap Assessments into one point-in-time `covered / total`, reusing the
    S3 `ResultQuery` for each mission's coverage (no new coverage machinery). Future Executive /
    Vendor / Compliance dashboards reuse this same provider."""

    def __init__(self, read_model: MissionListReadModel, result_query: ResultQuery) -> None:
        self._read_model = read_model
        self._result_query = result_query

    def snapshot(self, tenant: TenantContext) -> CoverageSnapshotView | None:
        page = self._read_model.list_missions(
            tenant,
            status=STATUS_COMPLETED,
            mission_type=MISSION_TYPE_GAP,
            page=1,
            page_size=COVERAGE_SCAN_LIMIT,
        )
        covered = total = assessments = 0
        for item in page.items:
            try:
                result = self._result_query.execute(item.mission_id, tenant)
            except DeliverableNotReady:
                # The snapshot said completed but the live mission is not — skip it (fail-safe).
                continue
            if result is None:
                continue
            content = result.content
            if isinstance(content, GapAssessmentContent):
                covered += content.coverage.covered_count
                total += content.coverage.total
                assessments += 1
        if assessments == 0 or total == 0:
            return None
        return CoverageSnapshotView(
            percent=covered / total, covered=covered, total=total, assessments=assessments
        )


class DashboardProjection:
    """The computed-on-read aggregation the Dashboard reads. Composes the two providers into one
    `DashboardView` — "system state now" for the caller's tenant. Entry point is `execute(...)`."""

    def __init__(
        self,
        mission_summary: MissionSummaryProvider,
        coverage_rollup: CoverageRollupProvider,
    ) -> None:
        self._mission_summary = mission_summary
        self._coverage_rollup = coverage_rollup

    def execute(self, tenant: TenantContext) -> DashboardView:
        waiting, running, failed, recent = self._mission_summary.summarize(tenant)
        coverage = self._coverage_rollup.snapshot(tenant)
        return DashboardView(
            waiting=waiting, running=running, failed=failed, recent=recent, coverage=coverage
        )
