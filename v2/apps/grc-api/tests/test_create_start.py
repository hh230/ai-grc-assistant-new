"""HTTP acceptance for New Mission — `POST /v1/missions` + `POST /v1/missions/{id}/run` (Slice S7).

The write side, end to end over real routes with the real Mission Catalog + engine: create a mission
from a type + scope (returns its plan for the review station), see it appear in the Mission List via
the existing projection, then **Start** it and watch it run — the whole `Create → Review Plan →
Start → (projections)` chain — plus type validation, tenant isolation, idempotency, and no Draft.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from grc_api.app import create_app
from grc_api.composition import Storage

from tests.conftest import AUTH_A, AUTH_B


def _client() -> TestClient:
    return TestClient(create_app(storage=Storage.MEMORY))


# --- create -----------------------------------------------------------------------------


def test_create_requires_auth() -> None:
    resp = _client().post("/v1/missions", json={"type": "gap_assessment", "scope": "X"})
    assert resp.status_code == 401


def test_create_returns_the_mission_and_its_plan_for_review() -> None:
    resp = _client().post(
        "/v1/missions", headers=AUTH_A, json={"type": "gap_assessment", "scope": "Technological"}
    )
    assert resp.status_code == 201
    body = resp.json()
    mission = body["mission"]
    assert mission["type"] == "gap_assessment" and mission["scope"] == "Technological"
    assert mission["status"] == "planned"  # created + planned = the pre-run "Draft"
    assert len(mission["plan"]) >= 1  # the human-readable plan, for the review station
    # product language, not internal step names
    assert mission["plan"][0]["description"] == "Identify applicable controls"
    # the review-station summary: steps to run, human approvals it will need
    assert body["steps"] == 3 and body["human_approvals"] == 0  # gap has no gate


def test_unknown_type_is_rejected() -> None:
    resp = _client().post("/v1/missions", headers=AUTH_A, json={"type": "nope", "scope": "X"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_created_mission_appears_in_the_list_via_the_projection() -> None:
    client = _client()
    created = client.post(
        "/v1/missions", headers=AUTH_A, json={"type": "risk_assessment", "scope": "Customer DB"}
    ).json()["mission"]
    rows = client.get("/v1/missions", headers=AUTH_A).json()["items"]
    assert [r["id"] for r in rows] == [created["id"]]  # fresh app: the only mission is the new one
    assert rows[0]["type"] == "risk_assessment" and rows[0]["scope"] == "Customer DB"


def test_create_is_tenant_scoped() -> None:
    client = _client()
    client.post("/v1/missions", headers=AUTH_A, json={"type": "gap_assessment", "scope": "A"})
    assert client.get("/v1/missions", headers=AUTH_B).json()["items"] == []


def test_create_is_idempotent_by_key() -> None:
    client = _client()
    headers = {**AUTH_A, "Idempotency-Key": "once"}
    first = client.post(
        "/v1/missions", headers=headers, json={"type": "gap_assessment", "scope": "A"}
    ).json()["mission"]
    second = client.post(
        "/v1/missions", headers=headers, json={"type": "gap_assessment", "scope": "A"}
    ).json()["mission"]
    assert first["id"] == second["id"]  # same mission, never a duplicate
    assert len(client.get("/v1/missions", headers=AUTH_A).json()["items"]) == 1


# --- start (the whole chain) ------------------------------------------------------------


def test_create_review_then_start_runs_the_mission() -> None:
    client = _client()
    created = client.post(
        "/v1/missions", headers=AUTH_A, json={"type": "gap_assessment", "scope": "Technological"}
    ).json()["mission"]
    assert created["status"] == "planned"  # review station: not auto-run

    started = client.post(f"/v1/missions/{created['id']}/run", headers=AUTH_A)
    assert started.status_code == 200
    # ADR 0055 / migration rule 10: the command's response describes the *command* — it does not
    # claim the execution it launched has finished. Execution runs behind MissionLaunchPort, so the
    # response must NOT assert "completed". This holds whether launch is synchronous, a worker, or a
    # queue — it is the boundary being tested, not a status value.
    assert started.json()["status"] != "completed"

    # Execution progress is read through a query, not the command response. The mission the command
    # launched has run to completion (echo executor, no gate), and the read surfaces reflect it.
    detail = client.get(f"/v1/missions/{created['id']}", headers=AUTH_A).json()
    assert detail["status"] == "completed"
    dash = client.get("/v1/dashboard", headers=AUTH_A).json()
    assert created["id"] in [r["id"] for r in dash["recent"]]


def test_starting_an_already_started_mission_is_409() -> None:
    client = _client()
    created = client.post(
        "/v1/missions", headers=AUTH_A, json={"type": "gap_assessment", "scope": "X"}
    ).json()["mission"]
    client.post(f"/v1/missions/{created['id']}/run", headers=AUTH_A)
    again = client.post(f"/v1/missions/{created['id']}/run", headers=AUTH_A)
    assert again.status_code == 409
