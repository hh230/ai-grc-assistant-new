"""The Approval API (S5a) — the four routes over ApprovalService, HTTP-level.

The API only ever *records* a decision in the shared store; applying it to the lifecycle is the
daemon's job. These tests prove the recording + the status codes (404 unknown, 409 already-decided,
400 no actor), and that the durable store reflects the decision with full actor identity.
"""

from __future__ import annotations

from pathlib import Path

from devteam_approval import ApprovalPolicy, ApprovalService, ApprovalStatus, FileApprovalStore
from fastapi.testclient import TestClient

from devteam_approval_api.app import create_app
from devteam_approval_api.config import ApprovalApiConfig


def _client(tmp_path: Path) -> tuple[TestClient, ApprovalService]:
    store = FileApprovalStore(tmp_path / "approvals.json")
    app = create_app(ApprovalApiConfig(store_path=tmp_path / "approvals.json"))
    return TestClient(app), ApprovalService(store)


def _open_gate(service: ApprovalService) -> str:
    request = service.create(
        target_ref="operations:example.com:site_down",
        resume_token="resume-1",
        policy=ApprovalPolicy("standard", "policy_owner", "Restart example.com — site is down"),
    )
    return request.id


def test_list_shows_pending_with_display_fields(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    _open_gate(service)
    body = client.get("/api/approvals").json()
    assert len(body["approvals"]) == 1
    view = body["approvals"][0]
    assert view["mission_type"] == "operations" and view["asset"] == "example.com"
    assert view["role"] == "policy_owner" and view["status"] == "pending"
    assert view["reason"].startswith("Restart example.com")


def test_grant_records_the_decision_with_actor_identity(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    request_id = _open_gate(service)

    res = client.post(
        f"/api/approvals/{request_id}/grant",
        json={"actor_id": "amiri", "actor_name": "Al Amiri", "role": "policy_owner"},
    )
    assert res.status_code == 200 and res.json()["status"] == "granted"

    # the durable store reflects it — this is exactly what the daemon will drain
    stored = service.get(request_id)
    assert stored is not None and stored.status is ApprovalStatus.GRANTED
    assert stored.current_decision is not None
    assert stored.current_decision.actor.actor_id == "amiri"
    assert stored.current_decision.actor.role == "policy_owner"
    assert client.get("/api/approvals").json()["approvals"] == []  # no longer pending


def test_reject_records_a_rejection(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    request_id = _open_gate(service)
    res = client.post(f"/api/approvals/{request_id}/reject", json={"actor_id": "amiri"})
    assert res.status_code == 200 and res.json()["status"] == "rejected"


def test_deciding_twice_conflicts_and_unknown_is_404(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    request_id = _open_gate(service)
    client.post(f"/api/approvals/{request_id}/grant", json={"actor_id": "a"})

    again = client.post(f"/api/approvals/{request_id}/grant", json={"actor_id": "a"})
    assert again.status_code == 409  # already decided → no longer pending

    missing = client.post("/api/approvals/nope/grant", json={"actor_id": "a"})
    assert missing.status_code == 404


def test_actor_id_is_required(tmp_path: Path) -> None:
    client, service = _client(tmp_path)
    request_id = _open_gate(service)
    res = client.post(f"/api/approvals/{request_id}/grant", json={"actor_id": "  "})
    assert res.status_code == 400
