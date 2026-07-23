"""S3 integration: GET /v1/missions/{id}/deliverable (the Result) and .../export — end to end via
the frozen Application contracts and the real `deliverables` package. A real Gap Assessment mission
is driven to completion with a scripted executor (controls + evidence), so the Result carries a real
coverage block and export produces real bytes."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from grc_api.app import create_app
from grc_api.composition import Storage
from mission_engine import InMemoryMissionStore, MissionEngine, Plan, PlanStep, StepResult
from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext

AUTH = {"Authorization": "Bearer dev-tenant-a"}
TENANT_A = TenantContext(tenant_id="tenant-a", principal_id="p")


class _Scripted:
    def __init__(self, scripted: list[tuple[str, tuple[str, ...]]]) -> None:
        self._scripted = scripted
        self._i = 0

    def execute(self, request: Any) -> StepResult:
        output, source_ids = self._scripted[self._i]
        self._i += 1
        return StepResult(step_id=request.step_id, ok=True, output=output, source_ids=source_ids)


def _gap_app() -> tuple[TestClient, str]:
    """An app with one COMPLETED Gap Assessment mission (A.8.5 covered, A.8.24 a gap)."""
    store = InMemoryMissionStore()
    scripted = _Scripted(
        [
            ("A.8.5 Secure authentication\nA.8.24 Use of cryptography",
             ("iso_27001:A.8.5", "iso_27001:A.8.24")),
            ("Acme implements secure authentication with hardware keys.", ("doc-acme-1",)),
            ("Authentication is covered; cryptography has no evidence.", ()),
        ]
    )
    engine = MissionEngine(store, scripted)
    mission = engine.create("gap assessment: Technological", TENANT_A)
    engine.plan(
        mission,
        Plan(steps=(
            PlanStep(description="identify_controls", instruction="Technological"),
            PlanStep(description="gather_evidence", instruction="Technological evidence"),
            PlanStep(description="compute_gap", instruction="compute the gap"),
        )),
    )
    engine.execute(mission)  # → COMPLETED
    read_model = InMemoryMissionListReadModel()
    read_model.record(
        MissionListItem(
            mission.id, "tenant-a", "gap_assessment", "Tech", mission.status.value, 1.0, 2.0
        )
    )
    app = create_app(
        storage=Storage.MEMORY,
        read_model=read_model,
        mission_store=store,
        mission_engine=engine,
    )
    return TestClient(app), mission.id


def _pending_app() -> tuple[TestClient, str]:
    """An app with a mission that is NOT completed (planned only) → the Result is not ready."""
    store = InMemoryMissionStore()
    engine = MissionEngine(store, _Scripted([]))
    mission = engine.create("gap assessment: Org", TENANT_A)
    engine.plan(mission, Plan(steps=(PlanStep(description="identify_controls", instruction="x"),)))
    read_model = InMemoryMissionListReadModel()
    read_model.record(
        MissionListItem(
            mission.id, "tenant-a", "gap_assessment", "Org", mission.status.value, 1.0, 2.0
        )
    )
    app = create_app(
        storage=Storage.MEMORY,
        read_model=read_model,
        mission_store=store,
        mission_engine=engine,
    )
    return TestClient(app), mission.id


# --- the Result -------------------------------------------------------------------------


def test_gap_result_has_trust_bar_sections_and_coverage() -> None:
    client, mission_id = _gap_app()
    body = client.get(f"/v1/missions/{mission_id}/deliverable", headers=AUTH).json()
    assert body["mission_id"] == mission_id
    # Trust Bar is the frame (the query's job), evidence-first.
    assert set(body["trust"]) == {"evidence_count", "human_review", "updated_at"}
    # Gap Assessment content: sections + a coverage block (Result adapts to the mission).
    assert body["content"]["kind"] == "gap_assessment"
    assert len(body["content"]["sections"]) == 3
    coverage = body["content"]["coverage"]
    assert coverage["framework"]  # a real framework name from the library
    assert coverage["total"] == 2 and coverage["covered_count"] == 1  # A.8.5 covered, A.8.24 a gap


def test_no_implementation_internals_in_the_result() -> None:
    client, mission_id = _gap_app()
    raw = client.get(f"/v1/missions/{mission_id}/deliverable", headers=AUTH).text
    assert "instruction" not in raw and "source_ids" not in raw and "goal" not in raw


def test_result_is_409_before_completed() -> None:
    client, mission_id = _pending_app()
    resp = client.get(f"/v1/missions/{mission_id}/deliverable", headers=AUTH)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_result_cross_tenant_is_404() -> None:
    client, mission_id = _gap_app()
    other = {"Authorization": "Bearer dev-tenant-b"}
    resp = client.get(f"/v1/missions/{mission_id}/deliverable", headers=other)
    assert resp.status_code == 404


# --- export -----------------------------------------------------------------------------


def test_export_markdown_returns_bytes() -> None:
    client, mission_id = _gap_app()
    resp = client.get(f"/v1/missions/{mission_id}/deliverable/export?format=md", headers=AUTH)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "attachment" in resp.headers["content-disposition"]
    assert len(resp.content) > 0


def test_export_pdf_returns_bytes() -> None:
    client, mission_id = _gap_app()
    resp = client.get(f"/v1/missions/{mission_id}/deliverable/export?format=pdf", headers=AUTH)
    assert resp.status_code == 200 and resp.content[:4] == b"%PDF"


def test_export_unknown_format_is_400() -> None:
    client, mission_id = _gap_app()
    resp = client.get(f"/v1/missions/{mission_id}/deliverable/export?format=xlsx", headers=AUTH)
    assert resp.status_code == 400
