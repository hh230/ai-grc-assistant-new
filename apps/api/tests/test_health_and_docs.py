"""Health probes and OpenAPI documentation are present and correct."""

from __future__ import annotations

import httpx


async def test_healthz_is_unauthenticated_and_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    # Correlation id is echoed for tracing.
    assert response.headers.get("x-request-id")


async def test_readyz_reports_capabilities(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["store_backend"] == "memory"
    assert body["llm_provider"] == "fake"
    assert body["registered_commands"] >= 50
    assert body["registered_queries"] >= 26


async def test_openapi_is_served_and_versioned(client: httpx.AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["version"] == "1.0.0"
    assert "/api/v1/missions" in spec["paths"]
    assert "/api/v1/orchestrator/runs" in spec["paths"]


async def test_inbound_request_id_is_preserved(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Request-Id": "trace-abc-123"})
    assert response.headers["x-request-id"] == "trace-abc-123"
