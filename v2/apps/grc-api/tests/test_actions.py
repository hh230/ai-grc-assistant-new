"""Integration tests for the write actions — one happy path per command **through the whole chain**:
HTTP → route → Application command → workflow adapter → Core engine → projection. Plus the error
mapping (403/404/409). A real (in-memory) engine drives a real gate to completion/cancellation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from grc_api.app import create_app
from grc_api.composition import Storage
from mission_engine import (
    EchoExecutor,
    InMemoryMissionStore,
    Mission,
    MissionEngine,
    Plan,
    PlanStep,
)
from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext

APPROVER = {"Authorization": "Bearer dev-approver-a"}
PRACTITIONER = {"Authorization": "Bearer dev-tenant-a"}
TENANT_A = TenantContext(tenant_id="tenant-a", principal_id="p")


def _gated_app() -> tuple[TestClient, Mission, InMemoryMissionListReadModel]:
    """An app whose store holds one mission paused at a human gate (a consequential step), with its
    Mission List projection seeded."""
    store = InMemoryMissionStore()
    engine = MissionEngine(store, EchoExecutor())
    mission = engine.create("Publish gap findings", TENANT_A)
    engine.plan(
        mission,
        Plan(steps=(PlanStep(description="Publish", instruction="do", consequential=True),)),
    )
    engine.execute(mission)  # drives to the gate → AWAITING_APPROVAL
    assert mission.has_active_approval

    read_model = InMemoryMissionListReadModel()
    read_model.record(
        MissionListItem(
            mission.id, "tenant-a", "gap_assessment", "Findings", mission.status.value, 1.0, 2.0
        )
    )
    app = create_app(
        storage=Storage.MEMORY,
        read_model=read_model,
        mission_store=store,
        mission_engine=engine,
    )
    return TestClient(app), mission, read_model


def _step_id(mission: Mission) -> str:
    return mission.plan.steps[0].id if mission.plan is not None else "s1"


# --- happy paths through the full chain -------------------------------------------------


def test_approve_completes_the_mission_and_updates_the_projection() -> None:
    client, mission, read_model = _gated_app()
    resp = client.post(
        f"/v1/missions/{mission.id}/approvals/{_step_id(mission)}/approve",
        headers=APPROVER,
        json={"comment": "looks good"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mission_id"] == mission.id
    # The command's response describes the *decision* (the gate was approved → the mission resumed),
    # not the execution that decision launched. Resuming past the gate runs behind the launch port,
    # so the response must not claim "completed" (migration rule 10 / ADR 0055). The approval is no
    # longer pending, whatever the launched execution then does.
    assert body["status"] != "completed"
    assert body["approval_pending"] is False
    # Execution progress is observed through a query. The resume the approval launched drove the
    # mission to completion, and the read model — projected by the launch — reflects it.
    detail = client.get(f"/v1/missions/{mission.id}", headers=APPROVER).json()
    assert detail["status"] == "completed"
    projected = read_model.get(mission.id, TENANT_A)
    assert projected is not None and projected.status == "completed"


def test_reject_cancels_the_mission_and_updates_the_projection() -> None:
    client, mission, read_model = _gated_app()
    resp = client.post(
        f"/v1/missions/{mission.id}/approvals/{_step_id(mission)}/reject",
        headers=APPROVER,
        json={"comment": "not yet"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"  # reject stops fail-safe
    projected = read_model.get(mission.id, TENANT_A)
    assert projected is not None and projected.status == "cancelled"


# --- error mapping ----------------------------------------------------------------------


def test_approve_without_approver_role_is_403() -> None:
    client, mission, _ = _gated_app()
    resp = client.post(
        f"/v1/missions/{mission.id}/approvals/{_step_id(mission)}/approve", headers=PRACTITIONER
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


def test_approve_missing_mission_is_404() -> None:
    client, _, _ = _gated_app()
    resp = client.post("/v1/missions/nope/approvals/s1/approve", headers=APPROVER)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_approve_when_not_awaiting_is_409() -> None:
    client, mission, _ = _gated_app()
    step = _step_id(mission)
    path = f"/v1/missions/{mission.id}/approvals/{step}/approve"
    client.post(path, headers=APPROVER)  # first approve completes the mission
    resp = client.post(path, headers=APPROVER)  # second: no longer awaiting
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_action_requires_auth() -> None:
    client, mission, _ = _gated_app()
    resp = client.post(f"/v1/missions/{mission.id}/approvals/{_step_id(mission)}/approve")
    assert resp.status_code == 401
