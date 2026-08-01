"""S5 acceptance for the Dashboard Projection — "What needs my attention right now?".

The projection is a computed-on-read aggregation composing two providers. These tests pin its
behaviour on the in-memory read model (no Postgres, no HTTP): the attention counts, the recently-
completed list (newest-first, any type), the Coverage Snapshot rolled up over *completed Gap
Assessments only*, tenant isolation, and the empty-coverage case. A tiny fake stands in for the S3
`ResultQuery` so coverage is deterministic without building real deliverables.
"""

from __future__ import annotations

from mission_application import (
    CoverageRollupProvider,
    CoverageView,
    DashboardProjection,
    GapAssessmentContent,
    MissionSummaryProvider,
    ResultView,
    TrustBar,
)
from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext


def tenant(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, principal_id="u", roles=("practitioner",), region="ksa"
    )


def item(
    mission_id: str,
    tenant_id: str,
    *,
    mission_type: str = "gap_assessment",
    status: str = "completed",
    updated_at: float = 100.0,
    title: str = "Scope",
) -> MissionListItem:
    return MissionListItem(
        mission_id, tenant_id, mission_type, title, status, 100.0, updated_at
    )


class _FakeResultQuery:
    """Maps mission_id → (covered, total); returns a ResultView carrying GapAssessmentContent so the
    CoverageRollupProvider can read coverage without the real deliverable machinery."""

    def __init__(self, coverage_by_id: dict[str, tuple[int, int]]) -> None:
        self._coverage = coverage_by_id

    def execute(self, mission_id: str, tenant: TenantContext) -> ResultView | None:
        if mission_id not in self._coverage:
            return None
        covered, total = self._coverage[mission_id]
        content = GapAssessmentContent(
            sections=(),
            coverage=CoverageView(
                framework="iso_27001",
                coverage=(covered / total) if total else 0.0,
                covered_count=covered,
                total=total,
                gaps=(),
            ),
        )
        return ResultView(
            mission_id=mission_id,
            title="x",
            trust=TrustBar(evidence_count=0, human_review="Not required", updated_at=100.0),
            content=content,
        )


def seed() -> InMemoryMissionListReadModel:
    rm = InMemoryMissionListReadModel()
    # tenant T: a spread of attention states + three completed missions (two gaps, one policy)
    rm.record(item("w1", "T", status="awaiting_approval", mission_type="vendor_review"))
    rm.record(item("r1", "T", status="executing"))
    rm.record(item("f1", "T", status="failed", mission_type="risk_assessment"))
    rm.record(item("c1", "T", status="completed", updated_at=300.0, title="Technological"))
    rm.record(item("c2", "T", status="completed", updated_at=200.0, title="Organizational"))
    rm.record(item("c3", "T", status="completed", mission_type="policy_generator", updated_at=250))
    # tenant T2: one waiting mission that must never leak into T's numbers
    rm.record(item("x1", "T2", status="awaiting_approval"))
    return rm


# --- attention counts -------------------------------------------------------------------


def test_attention_counts_map_status_to_words() -> None:
    summary = MissionSummaryProvider(seed())
    waiting, running, failed, _recent = summary.summarize(tenant("T"))
    assert (waiting, running, failed) == (1, 1, 1)


def test_counts_are_tenant_scoped() -> None:
    summary = MissionSummaryProvider(seed())
    waiting, running, failed, recent = summary.summarize(tenant("T2"))
    assert (waiting, running, failed) == (1, 0, 0)
    assert recent == ()  # T2 has no completed missions


# --- recently completed -----------------------------------------------------------------


def test_recent_is_completed_any_type_newest_first() -> None:
    summary = MissionSummaryProvider(seed())
    _w, _r, _f, recent = summary.summarize(tenant("T"))
    # c1 (300) · c3 (250, a policy — completed counts regardless of type) · c2 (200)
    assert [r.mission_id for r in recent] == ["c1", "c3", "c2"]


# --- coverage snapshot (rollup over completed Gap Assessments only) ----------------------


def test_coverage_snapshot_rolls_up_only_gap_assessments() -> None:
    # c1 and c2 are completed gaps; c3 is a completed policy (excluded before ResultQuery is asked).
    fake = _FakeResultQuery({"c1": (5, 10), "c2": (3, 10)})
    rollup = CoverageRollupProvider(seed(), fake)
    snap = rollup.snapshot(tenant("T"))
    assert snap is not None
    assert (snap.covered, snap.total, snap.assessments) == (8, 20, 2)
    assert abs(snap.percent - 0.4) < 1e-9


def test_coverage_is_none_when_no_completed_gap_assessments() -> None:
    rm = InMemoryMissionListReadModel()
    rm.record(item("p1", "T", status="completed", mission_type="policy_generator"))
    rm.record(item("g1", "T", status="executing"))  # a gap, but not completed
    rollup = CoverageRollupProvider(rm, _FakeResultQuery({}))
    assert rollup.snapshot(tenant("T")) is None


def test_coverage_is_tenant_scoped() -> None:
    fake = _FakeResultQuery({"c1": (5, 10), "c2": (3, 10)})
    rollup = CoverageRollupProvider(seed(), fake)
    assert rollup.snapshot(tenant("T2")) is None  # T2 has no completed gaps


# --- the whole projection ---------------------------------------------------------------


def test_projection_assembles_system_state_now() -> None:
    rm = seed()
    projection = DashboardProjection(
        MissionSummaryProvider(rm),
        CoverageRollupProvider(rm, _FakeResultQuery({"c1": (5, 10), "c2": (3, 10)})),
    )
    view = projection.execute(tenant("T"))
    assert (view.waiting, view.running, view.failed) == (1, 1, 1)
    assert [r.mission_id for r in view.recent] == ["c1", "c3", "c2"]
    assert view.coverage is not None and view.coverage.covered == 8

    # a fresh tenant sees an empty, honest dashboard — not another tenant's numbers
    empty = projection.execute(tenant("nobody"))
    assert (empty.waiting, empty.running, empty.failed) == (0, 0, 0)
    assert empty.recent == () and empty.coverage is None
