"""Shared test fixtures: a wired API app with deterministic multi-tenant principals.

Tests drive the real ASGI app through httpx (the "API" caller of CLAUDE.md §9), with the
in-memory store and the deterministic fake LLM — no network, no database, no secrets.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
import pytest
from grc_api.app import create_app
from grc_api.settings import Settings

# Deterministic principals across two tenants and several roles.
TOKENS = {
    "owner-org1": {"user_id": "u-owner-1", "organization_id": "org-1", "roles": ["owner"]},
    "analyst-org1": {"user_id": "u-analyst-1", "organization_id": "org-1", "roles": ["analyst"]},
    "viewer-org1": {"user_id": "u-viewer-1", "organization_id": "org-1", "roles": ["viewer"]},
    "owner-org2": {"user_id": "u-owner-2", "organization_id": "org-2", "roles": ["owner"]},
}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app_env="testing",
        llm_provider="fake",
        store_backend="memory",
        auth_seed_dev_principal=False,
        api_auth_tokens=json.dumps(TOKENS),
        log_json=False,
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
