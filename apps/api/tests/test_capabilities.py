"""Cross-context capability smoke tests: each router maps HTTP ↔ use case correctly."""

from __future__ import annotations

import httpx
from conftest import auth

OWNER = "owner-org1"


async def test_framework_import_publish_and_list(client: httpx.AsyncClient) -> None:
    imported = await client.post(
        "/api/v1/frameworks",
        json={
            "framework_id": "framework:iso_27001",
            "name": "ISO/IEC 27001",
            "version": "2022",
            "region": "global",
            "languages": ["en"],
            "controls": [
                {
                    "id": "A.5.1",
                    "code": "A.5.1",
                    "title": "Policies for information security",
                    "domain": "Organizational",
                    "requirements": [{"code": "A.5.1.1", "text": "Define security policies."}],
                }
            ],
        },
        headers=auth(OWNER),
    )
    assert imported.status_code == 201
    assert imported.json()["control_count"] == 1

    published = await client.post(
        "/api/v1/frameworks/framework:iso_27001/publish",
        json={"version": "2022"},
        headers=auth(OWNER),
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    listed = await client.get("/api/v1/frameworks", headers=auth(OWNER))
    assert listed.status_code == 200
    assert any(fw["id"] == "framework:iso_27001" for fw in listed.json())


async def test_control_then_status_update(client: httpx.AsyncClient) -> None:
    workspace = await client.post("/api/v1/workspaces", json={"name": "WS"}, headers=auth(OWNER))
    workspace_id = workspace.json()["id"]
    control = await client.post(
        "/api/v1/controls",
        json={"workspace_id": workspace_id, "title": "Access Control"},
        headers=auth(OWNER),
    )
    assert control.status_code == 201
    control_id = control.json()["id"]

    updated = await client.put(
        f"/api/v1/controls/{control_id}/implementation-status",
        json={"status": "implemented"},
        headers=auth(OWNER),
    )
    assert updated.status_code == 200
    assert updated.json()["implementation_status"] == "implemented"

    listed = await client.get(
        "/api/v1/controls", params={"workspace_id": workspace_id}, headers=auth(OWNER)
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_risk_lifecycle(client: httpx.AsyncClient) -> None:
    risk = await client.post(
        "/api/v1/risks",
        json={"title": "Unpatched servers", "category": "technical"},
        headers=auth(OWNER),
    )
    assert risk.status_code == 201
    risk_id = risk.json()["id"]

    assessed = await client.post(
        f"/api/v1/risks/{risk_id}/assessment",
        json={"likelihood": 4, "impact": 5},
        headers=auth(OWNER),
    )
    assert assessed.status_code == 200
    assert assessed.json()["score"] == 20
    assert assessed.json()["level"] in {"high", "critical"}


async def test_invalid_enum_is_422_problem(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/risks",
        json={"title": "x"},
        headers=auth(OWNER),
    )
    # title ok, but a bad enum elsewhere:
    bad = await client.post(
        "/api/v1/evidence",
        json={"title": "doc", "evidence_type": "not-a-type"},
        headers=auth(OWNER),
    )
    assert response.status_code == 201
    assert bad.status_code == 422
    body = bad.json()
    assert body["code"] == "request_validation_error"
    assert body["status"] == 422
    assert "errors" in body


async def test_tool_registration_and_listing(client: httpx.AsyncClient) -> None:
    registered = await client.post(
        "/api/v1/tools",
        json={
            "name": "analyze_control_gap",
            "version": "2.0.0",
            "description": "Analyze control gaps for a framework.",
            "side_effect": "read_only",
            "required_permissions": ["controls:read"],
        },
        headers=auth(OWNER),
    )
    assert registered.status_code == 201
    assert registered.json()["requires_approval"] is False

    listed = await client.get("/api/v1/tools", headers=auth(OWNER))
    assert listed.status_code == 200
    assert any(tool["name"] == "analyze_control_gap" for tool in listed.json())


async def test_audit_append_and_query(client: httpx.AsyncClient) -> None:
    appended = await client.post(
        "/api/v1/audit",
        json={
            "category": "state_change",
            "action": "control.updated",
            "object_type": "control",
            "object_id": "ctrl-1",
            "outcome": "success",
        },
        headers=auth(OWNER),
    )
    assert appended.status_code == 201
    assert appended.json()["actor_kind"] == "user"

    queried = await client.get(
        "/api/v1/audit", params={"object_type": "control"}, headers=auth(OWNER)
    )
    assert queried.status_code == 200
    assert len(queried.json()) == 1
    assert queried.json()[0]["object_id"] == "ctrl-1"
