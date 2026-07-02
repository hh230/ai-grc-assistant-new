"""Idempotency-Key makes consequential POSTs safe to retry (Handbook §8.116)."""

from __future__ import annotations

import httpx
from conftest import auth


async def test_repeated_post_with_key_replays_first_response(client: httpx.AsyncClient) -> None:
    headers = {**auth("owner-org1"), "Idempotency-Key": "create-ws-001"}
    first = await client.post("/api/v1/workspaces", json={"name": "Idem WS"}, headers=headers)
    assert first.status_code == 201
    assert "idempotency-replayed" not in first.headers
    first_id = first.json()["id"]

    second = await client.post("/api/v1/workspaces", json={"name": "Idem WS"}, headers=headers)
    assert second.status_code == 201
    assert second.headers.get("idempotency-replayed") == "true"
    # Same response replayed -> no second workspace was created.
    assert second.json()["id"] == first_id

    listed = await client.get("/api/v1/workspaces", headers=auth("owner-org1"))
    assert len(listed.json()) == 1


async def test_without_key_each_post_is_independent(client: httpx.AsyncClient) -> None:
    headers = auth("owner-org1")
    a = await client.post("/api/v1/workspaces", json={"name": "A"}, headers=headers)
    b = await client.post("/api/v1/workspaces", json={"name": "A"}, headers=headers)
    assert a.json()["id"] != b.json()["id"]


async def test_key_is_scoped_per_credential(client: httpx.AsyncClient) -> None:
    # Same key, different tenants -> no cross-tenant replay/leak.
    h1 = {**auth("owner-org1"), "Idempotency-Key": "shared-key"}
    h2 = {**auth("owner-org2"), "Idempotency-Key": "shared-key"}
    r1 = await client.post("/api/v1/workspaces", json={"name": "T1"}, headers=h1)
    r2 = await client.post("/api/v1/workspaces", json={"name": "T2"}, headers=h2)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert "idempotency-replayed" not in r2.headers
    assert r1.json()["organization_id"] == "org-1"
    assert r2.json()["organization_id"] == "org-2"
