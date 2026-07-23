"""S2 acceptance for GET /v1/missions/{id}: a **View Model** (no aggregate internals), composed from
live Core state + read-model type/scope, tenant-scoped fail-closed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from grc_api.app import create_app
from grc_api.composition import Storage
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

TENANT_A = TenantContext(
    tenant_id="tenant-a", principal_id="practitioner@a", roles=("practitioner",), region="ksa"
)
AUTH_A = {"Authorization": "Bearer dev-tenant-a"}
AUTH_B = {"Authorization": "Bearer dev-tenant-b"}


def _running_mission_with_finding() -> tuple[Mission, str]:
    mission = Mission.create(goal="Gap on ISO A.8", tenant=TENANT_A)
    step = PlanStep(
        description="Collect evidence", instruction="SECRET-INSTRUCTION", tool="local_search"
    )
    mission.set_plan(Plan(steps=(step,)))
    mission.begin_execution()
    mission.record_step(
        StepResult(
            step_id=step.id,
            ok=True,
            output="Found 3 relevant controls",
            citations=("iso:A.8.5",),
            confidence=0.8,
            source_ids=("chunk-42",),
        )
    )
    return mission, step.id


def _awaiting_mission() -> Mission:
    mission = Mission.create(goal="Publish gap findings", tenant=TENANT_A)
    mission.set_plan(Plan(steps=(PlanStep(description="Compare evidence", instruction="x"),)))
    mission.begin_execution()
    mission.await_approval(ApprovalRequest(reason="publish gap findings", requested_by="analyst@a"))
    return mission


@pytest.fixture
def client() -> tuple[TestClient, Mission, str, Mission]:
    store = InMemoryMissionStore()
    rm = InMemoryMissionListReadModel()

    running, step_id = _running_mission_with_finding()
    awaiting = _awaiting_mission()
    for m, mtype, scope in [
        (running, "gap_assessment", "Technological controls"),
        (awaiting, "gap_assessment", "Publish findings"),
    ]:
        store.save(m)
        rm.record(MissionListItem(m.id, "tenant-a", mtype, scope, m.status.value, 1.0, 2.0))

    app = create_app(storage=Storage.MEMORY, read_model=rm, mission_store=store)
    return TestClient(app), running, step_id, awaiting


def test_returns_view_model_with_type_scope_and_findings(client) -> None:  # type: ignore[no-untyped-def]
    tc, running, step_id, _ = client
    body = tc.get(f"/v1/missions/{running.id}", headers=AUTH_A).json()
    assert body["id"] == running.id
    assert body["type"] == "gap_assessment"
    assert body["scope"] == "Technological controls"
    assert body["status"] == "executing"
    assert body["plan"] == [{"id": step_id, "description": "Collect evidence"}]
    assert body["findings"][0]["title"] == "Collect evidence"
    assert body["findings"][0]["summary"] == "Found 3 relevant controls"
    assert body["findings"][0]["citations"] == ["iso:A.8.5"]
    assert body["findings"][0]["confidence"] == 0.8


def test_no_implementation_internals_leak(client) -> None:  # type: ignore[no-untyped-def]
    tc, running, _, _ = client
    raw = tc.get(f"/v1/missions/{running.id}", headers=AUTH_A).text
    # Constraint 2: the tool name, the instruction, and the source (chunk) id must never appear.
    assert "local_search" not in raw
    assert "SECRET-INSTRUCTION" not in raw
    assert "chunk-42" not in raw
    assert "source_ids" not in raw and "instruction" not in raw and "tool" not in raw


def test_pending_approval_renders_as_gate(client) -> None:  # type: ignore[no-untyped-def]
    tc, _, _, awaiting = client
    body = tc.get(f"/v1/missions/{awaiting.id}", headers=AUTH_A).json()
    assert body["status"] == "awaiting_approval"
    assert body["approval"]["proposed_action"] == "publish gap findings"
    assert body["approval"]["status"] == "pending"


def test_cross_tenant_is_404(client) -> None:  # type: ignore[no-untyped-def]
    tc, running, _, _ = client
    # tenant-b asking for tenant-a's mission: existence is not revealed.
    resp = tc.get(f"/v1/missions/{running.id}", headers=AUTH_B)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_missing_is_404(client) -> None:  # type: ignore[no-untyped-def]
    tc, _, _, _ = client
    assert tc.get("/v1/missions/does-not-exist", headers=AUTH_A).status_code == 404


def test_detail_requires_auth(client) -> None:  # type: ignore[no-untyped-def]
    tc, running, _, _ = client
    assert tc.get(f"/v1/missions/{running.id}").status_code == 401
