"""Authentication, RBAC (default deny), and absolute tenant isolation at the HTTP boundary."""

from __future__ import annotations

import httpx
from conftest import auth


async def test_missing_token_is_401_problem_json(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/workspaces")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "authentication_required"
    assert body["status"] == 401


async def test_invalid_token_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/workspaces", headers=auth("not-a-real-token"))
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


async def test_viewer_cannot_create_workspace_403(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/workspaces", json={"name": "Blocked"}, headers=auth("viewer-org1")
    )
    assert response.status_code == 403
    assert response.json()["code"] == "authorization_error"


async def test_viewer_can_read(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/workspaces", headers=auth("viewer-org1"))
    assert response.status_code == 200
    assert response.json() == []


async def test_tenant_isolation_get_across_orgs_is_404(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/api/v1/workspaces", json={"name": "Org1 WS"}, headers=auth("owner-org1")
    )
    assert created.status_code == 201
    workspace_id = created.json()["id"]

    # Same id, different tenant -> default deny -> not found (no existence leak).
    cross = await client.get(f"/api/v1/workspaces/{workspace_id}", headers=auth("owner-org2"))
    assert cross.status_code == 404

    # Owner of org-2 sees an empty list, never org-1's data.
    listed = await client.get("/api/v1/workspaces", headers=auth("owner-org2"))
    assert listed.status_code == 200
    assert listed.json() == []


async def test_list_is_scoped_to_tenant(client: httpx.AsyncClient) -> None:
    await client.post("/api/v1/workspaces", json={"name": "A"}, headers=auth("owner-org1"))
    await client.post("/api/v1/workspaces", json={"name": "B"}, headers=auth("owner-org1"))
    listed = await client.get("/api/v1/workspaces", headers=auth("owner-org1"))
    assert listed.status_code == 200
    assert {ws["name"] for ws in listed.json()} == {"A", "B"}
