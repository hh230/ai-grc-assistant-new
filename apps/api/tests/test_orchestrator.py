"""The governed AI Orchestrator endpoint: routing, transparency, and human gates."""

from __future__ import annotations

import httpx
from conftest import auth


async def test_orchestrator_routes_and_holds_consequential_output(
    client: httpx.AsyncClient,
) -> None:
    # A policy goal routes to the Policy agent, whose output is consequential -> human gate.
    response = await client.post(
        "/api/v1/orchestrator/runs",
        json={"goal": "Draft a data retention policy for PDPL"},
        headers=auth("owner-org1"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "policy"
    assert body["awaiting_approval"] is True
    assert body["result"]["requires_human_approval"] is True
    # The decision trail is exposed for transparency (CLAUDE.md §19).
    steps = {d["step"] for d in body["decisions"]}
    assert {"plan", "execute", "human_gate"} <= steps


async def test_orchestrator_read_only_route_not_gated(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/orchestrator/runs",
        json={"goal": "Run a control gap analysis against ISO 27001"},
        headers=auth("owner-org1"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "compliance"
    assert body["awaiting_approval"] is False


async def test_orchestrator_requires_execute_permission(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/orchestrator/runs",
        json={"goal": "Draft a policy"},
        headers=auth("viewer-org1"),
    )
    assert response.status_code == 403


async def test_orchestrator_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/orchestrator/runs", json={"goal": "x"})
    assert response.status_code == 401
