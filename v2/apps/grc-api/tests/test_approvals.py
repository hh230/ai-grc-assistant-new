"""HTTP acceptance for Decisions — `GET /v1/approvals` (Slice S6).

"What decisions are waiting for me?" over real routes: fail-closed auth, one Decision per waiting
approval (proposed action · mission context · waiting-since · evidence · the reference to act on),
tenant isolation, and — reusing the S2 command — the decision **leaving the list** once it is made.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from grc_api.app import create_app
from mission_engine import InMemoryMissionStore, MissionEngine, Plan, PlanStep, StepResult
from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext

from tests.conftest import AUTH_A, AUTH_B

AUTH_APPROVER = {"Authorization": "Bearer dev-approver-a"}  # tenant-a + the Approver role


class _GatherExecutor:
    def execute(self, request: Any) -> StepResult:
        return StepResult(
            step_id=request.step_id, ok=True, output="gathered", citations=("doc-1", "doc-2")
        )


def _app_with_waiting_decision() -> tuple[TestClient, str]:
    store = InMemoryMissionStore()
    read_model = InMemoryMissionListReadModel()
    engine = MissionEngine(store, _GatherExecutor())
    ctx = TenantContext(tenant_id="tenant-a", principal_id="system")
    mission = engine.create("vendor_review: Vendor Acme", ctx)
    engine.plan(
        mission,
        Plan(
            steps=(
                PlanStep(description="Gather evidence", instruction="do"),
                PlanStep(description="Publish findings", instruction="do", consequential=True),
            )
        ),
    )
    engine.execute(mission)  # → AWAITING_APPROVAL
    read_model.record(
        MissionListItem(
            mission.id, "tenant-a", "vendor_review", "Vendor Acme", mission.status.value,
            mission.created_at, mission.updated_at,
        )
    )
    client = TestClient(
        create_app(read_model=read_model, mission_store=store, mission_engine=engine)
    )
    return client, mission.id


# --- auth ---------------------------------------------------------------------------------


def test_requires_auth() -> None:
    client, _ = _app_with_waiting_decision()
    assert client.get("/v1/approvals").status_code == 401


# --- the decision carries what a person needs ------------------------------------------


def test_lists_a_decision_not_a_mission_row() -> None:
    client, mission_id = _app_with_waiting_decision()
    items = client.get("/v1/approvals?status=waiting", headers=AUTH_A).json()["items"]
    assert len(items) == 1
    d = items[0]
    assert d["mission_id"] == mission_id
    assert d["proposed_action"] == "Publish findings"
    assert d["mission_type"] == "vendor_review" and d["mission_scope"] == "Vendor Acme"
    assert d["evidence_count"] == 2
    assert d["decision_id"]  # the reference Approve/Reject acts on
    assert "step_id" not in d  # no implementation detail leaks


# --- tenant isolation -------------------------------------------------------------------


def test_one_tenant_never_sees_anothers_decisions() -> None:
    client, _ = _app_with_waiting_decision()
    assert client.get("/v1/approvals", headers=AUTH_B).json() == {"items": []}


# --- deciding (reused S2 command) removes it from the list ------------------------------


def test_approving_removes_the_decision_from_the_list() -> None:
    client, mission_id = _app_with_waiting_decision()
    decision = client.get("/v1/approvals", headers=AUTH_A).json()["items"][0]

    # Reuse the S2 approve command — the URL's {step_id} is the decision reference.
    resp = client.post(
        f"/v1/missions/{mission_id}/approvals/{decision['decision_id']}/approve",
        headers=AUTH_APPROVER,
        json={"comment": "looks good"},
    )
    assert resp.status_code == 200

    # The mission resumed → the decision is no longer waiting.
    assert client.get("/v1/approvals", headers=AUTH_A).json() == {"items": []}


def test_a_made_decision_appears_in_recent() -> None:
    client, mission_id = _app_with_waiting_decision()
    decision = client.get("/v1/approvals", headers=AUTH_A).json()["items"][0]
    client.post(
        f"/v1/missions/{mission_id}/approvals/{decision['decision_id']}/approve",
        headers=AUTH_APPROVER,
        json={"comment": ""},
    )
    # When nothing is waiting, the page stays alive with the recent decisions (a read-only history).
    recent = client.get("/v1/approvals?status=decided", headers=AUTH_A).json()["items"]
    assert len(recent) == 1
    assert recent[0]["proposed_action"] == "Publish findings"
    assert recent[0]["approved"] is True
