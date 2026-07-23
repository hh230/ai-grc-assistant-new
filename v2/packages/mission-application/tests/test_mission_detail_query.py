"""Unit tests for MissionDetailQuery — the mapping + composition, no HTTP.

Proves the View Model hides implementation (constraint 2), composes Core + read model, and is
tenant-scoped fail-closed — all at the Application layer, so the HTTP host only needs a thin
behavioural test."""

from __future__ import annotations

from mission_application import MissionDetailQuery
from mission_engine import (
    ApprovalRequest,
    InMemoryMissionStore,
    Mission,
    Plan,
    PlanStep,
    StepResult,
)
from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext

TENANT = TenantContext(tenant_id="T", principal_id="u", roles=("practitioner",), region="ksa")
OTHER = TenantContext(tenant_id="T2", principal_id="u2", roles=(), region="ksa")


def _running() -> tuple[Mission, str]:
    m = Mission.create(goal="Gap", tenant=TENANT)
    step = PlanStep(description="Collect evidence", instruction="SECRET", tool="local_search")
    m.set_plan(Plan(steps=(step,)))
    m.begin_execution()
    m.record_step(
        StepResult(
            step_id=step.id,
            output="Found 3 controls",
            citations=("iso:A.8.5",),
            confidence=0.8,
            source_ids=("chunk-42",),
        )
    )
    return m, step.id


def _query_over(*missions: Mission) -> MissionDetailQuery:
    store = InMemoryMissionStore()
    rm = InMemoryMissionListReadModel()
    for m in missions:
        store.save(m)
        rm.record(
            MissionListItem(
                m.id, m.tenant_id, "gap_assessment", "Tech controls", m.status.value, 1.0, 2.0
            )
        )
    return MissionDetailQuery(store, rm)


def test_composes_view_with_type_scope_and_findings() -> None:
    m, step_id = _running()
    view = _query_over(m).execute(m.id, TENANT)
    assert view is not None
    assert view.type == "gap_assessment" and view.scope == "Tech controls"
    assert view.status == "executing"
    assert view.plan == (view.plan[0],) and view.plan[0].id == step_id
    assert view.plan[0].description == "Collect evidence"
    assert view.findings[0].title == "Collect evidence"
    assert view.findings[0].citations == ("iso:A.8.5",)
    assert view.findings[0].confidence == 0.8


def test_view_has_no_internal_fields() -> None:
    m, _ = _running()
    view = _query_over(m).execute(m.id, TENANT)
    assert view is not None
    # The View Model dataclasses simply have no place to carry these — assert the shape.
    assert set(vars(view.plan[0])) == {"id", "description"}
    assert set(vars(view.findings[0])) == {"step_id", "title", "summary", "citations", "confidence"}


def test_pending_approval_becomes_a_gate() -> None:
    m = Mission.create(goal="Publish", tenant=TENANT)
    m.set_plan(Plan(steps=(PlanStep(description="Compare", instruction="x"),)))
    m.begin_execution()
    m.await_approval(ApprovalRequest(reason="publish findings", requested_by="a"))
    view = _query_over(m).execute(m.id, TENANT)
    assert view is not None and view.approval is not None
    assert view.approval.proposed_action == "publish findings"
    assert view.approval.status == "pending"


def test_missing_returns_none() -> None:
    assert _query_over().execute("nope", TENANT) is None


def test_cross_tenant_returns_none() -> None:
    m, _ = _running()
    assert _query_over(m).execute(m.id, OTHER) is None
