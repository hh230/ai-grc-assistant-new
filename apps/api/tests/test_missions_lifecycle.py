"""End-to-end mission lifecycle through the API, including the human-gate path (CLAUDE.md §8)."""

from __future__ import annotations

import httpx
from conftest import auth


async def _create_workspace(client: httpx.AsyncClient, token: str) -> str:
    response = await client.post(
        "/api/v1/workspaces", json={"name": "Compliance WS"}, headers=auth(token)
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_full_mission_lifecycle_with_human_gate(client: httpx.AsyncClient) -> None:
    token = "owner-org1"
    workspace_id = await _create_workspace(client, token)

    # Create
    created = await client.post(
        "/api/v1/missions",
        json={"workspace_id": workspace_id, "goal": "SOC 2 gap analysis"},
        headers=auth(token),
    )
    assert created.status_code == 201
    mission = created.json()
    mission_id = mission["id"]
    assert mission["status"] == "created"

    # Plan with a consequential step
    planned = await client.post(
        f"/api/v1/missions/{mission_id}/plan",
        json={"steps": [{"name": "draft remediation", "side_effect": "consequential"}]},
        headers=auth(token),
    )
    assert planned.status_code == 200
    step_id = planned.json()["steps"][0]["id"]

    # Start mission + step
    assert (
        await client.post(f"/api/v1/missions/{mission_id}/start", headers=auth(token))
    ).status_code == 200
    started_step = await client.post(
        f"/api/v1/missions/{mission_id}/steps/{step_id}/start", headers=auth(token)
    )
    assert started_step.status_code == 200

    # Open a human gate for the consequential step
    gated = await client.post(
        f"/api/v1/missions/{mission_id}/steps/{step_id}/request-approval",
        json={"action_description": "apply remediation to production controls"},
        headers=auth(token),
    )
    assert gated.status_code == 200
    gate_id = gated.json()["approval_gates"][0]["id"]

    # Approve the gate (the human decision)
    approved = await client.post(
        f"/api/v1/missions/{mission_id}/gates/{gate_id}/approve", headers=auth(token)
    )
    assert approved.status_code == 200
    gate = approved.json()["approval_gates"][0]
    assert gate["decision"] == "approved"
    assert gate["decided_by"] == "u-owner-1"


async def test_get_unknown_mission_is_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/missions/does-not-exist", headers=auth("owner-org1"))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_list_missions_requires_workspace_param(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/missions", headers=auth("owner-org1"))
    assert response.status_code == 422  # missing required query param


async def test_analyst_can_drive_a_mission(client: httpx.AsyncClient) -> None:
    workspace_id = await _create_workspace(client, "owner-org1")
    created = await client.post(
        "/api/v1/missions",
        json={"workspace_id": workspace_id, "goal": "evidence sweep"},
        headers=auth("analyst-org1"),
    )
    assert created.status_code == 201
