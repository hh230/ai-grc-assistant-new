"""HTTP acceptance for the Dashboard — `GET /v1/dashboard` (Slice S5).

"What needs my attention right now?" over real routes: fail-closed auth, attention counts that
reconcile with the Missions list (same read model), tenant isolation, and — end to end through a
real completed Gap Assessment — a non-null Coverage Snapshot. The seeded `client` has no completed
Gap Assessment, so its coverage is null (honest); a dedicated app drives one to prove the rollup.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from grc_api.app import create_app
from grc_api.composition import Storage
from mission_engine import InMemoryMissionStore, MissionEngine, Plan, PlanStep, StepResult
from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext

from tests.conftest import AUTH_A, AUTH_B

# --- auth + shape (seeded client: coverage is null, no completed Gap Assessment) ---------


def test_dashboard_requires_auth(client: TestClient) -> None:
    assert client.get("/v1/dashboard").status_code == 401


def test_attention_counts_and_recent(client: TestClient) -> None:
    body = client.get("/v1/dashboard", headers=AUTH_A).json()
    # tenant-a seed: m3 awaiting_approval · m1 executing · m2 completed(risk) → no completed gap.
    assert body["waiting"] == 1
    assert body["running"] == 1
    assert body["failed"] == 0
    assert [r["id"] for r in body["recent"]] == ["m2"]
    assert body["coverage"] is None  # honest: no completed Gap Assessment yet


def test_counts_are_tenant_scoped(client: TestClient) -> None:
    a = client.get("/v1/dashboard", headers=AUTH_A).json()
    b = client.get("/v1/dashboard", headers=AUTH_B).json()
    # tenant-b seed: x1 executing · x2 completed(policy); no awaiting_approval.
    assert (b["waiting"], b["running"]) == (0, 1)
    assert [r["id"] for r in b["recent"]] == ["x2"]
    assert a != b  # each tenant sees its own system-state


def test_waiting_count_reconciles_with_the_missions_list(client: TestClient) -> None:
    dash = client.get("/v1/dashboard", headers=AUTH_A).json()
    listed = client.get("/v1/missions?status=awaiting_approval", headers=AUTH_A).json()
    assert dash["waiting"] == listed["total"]


# --- coverage snapshot, end to end through a real completed Gap Assessment ---------------


class _ScriptedExecutor:
    """Drives a gap mission to real control ids + evidence so its Result carries a coverage grid."""

    def __init__(self, scripted: list[tuple[str, tuple[str, ...]]]) -> None:
        self._scripted = scripted
        self._i = 0

    def execute(self, request: Any) -> StepResult:
        output, source_ids = self._scripted[self._i]
        self._i += 1
        return StepResult(step_id=request.step_id, ok=True, output=output, source_ids=source_ids)


def _step(description: str) -> PlanStep:
    return PlanStep(description=description, instruction="do", consequential=False)


def _app_with_completed_gap() -> TestClient:
    store = InMemoryMissionStore()
    read_model = InMemoryMissionListReadModel()
    engine = MissionEngine(
        store,
        _ScriptedExecutor(
            [
                ("A.8.5 Secure authentication\nA.8.24 Use of cryptography",
                 ("iso_27001:A.8.5", "iso_27001:A.8.24")),
                ("Acme implements secure authentication with hardware keys.", ("doc-acme-1",)),
                ("Authentication is covered; cryptography has no supporting evidence.", ()),
            ]
        ),
    )
    tenant = TenantContext(tenant_id="tenant-a", principal_id="system")
    mission = engine.create("gap assessment: Technological", tenant)
    engine.plan(
        mission,
        Plan(steps=(_step("identify_controls"), _step("gather_evidence"), _step("compute_gap"))),
    )
    engine.execute(mission)
    read_model.record(
        MissionListItem(
            mission.id, "tenant-a", "gap_assessment", "Technological", mission.status.value,
            mission.created_at, mission.updated_at,
        )
    )
    return TestClient(create_app(
        storage=Storage.MEMORY,
        read_model=read_model,
        mission_store=store,
        mission_engine=engine,
    ))


def test_coverage_snapshot_flows_end_to_end() -> None:
    body = _app_with_completed_gap().get("/v1/dashboard", headers=AUTH_A).json()
    coverage = body["coverage"]
    assert coverage is not None
    # One completed Gap Assessment: 2 controls, 1 covered by evidence → 50%.
    assert coverage["assessments"] == 1
    assert coverage["total"] == 2 and coverage["covered"] == 1
    assert abs(coverage["percent"] - 0.5) < 1e-9
