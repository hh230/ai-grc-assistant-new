"""Integration tests for the Policy Intelligence router (PI-P5, ADR-0022): Policy Hunter's
obligations/coverage-gaps endpoints and Policy Analyst's quality-review endpoint, driven
through the real ASGI app against apps/web's live Postgres schema.

Needs a real database with apps/web's migrations applied (same convention as
``packages/persistence-web`` and ``test_web_runtime.py``): point ``TEST_DATABASE_URL``
(or ``DATABASE_URL``) at one, or these tests skip cleanly.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from grc_api.app import create_app
from grc_api.security.dependencies import get_authz
from grc_api.settings import Settings
from grc_persistence_web import (
    Database,
    PolicyRepository,
    RegulatoryObligationRepository,
    RegulatoryRawDocumentRepository,
)
from grc_services.shared.authorization import Action, AuthorizationService, ResourceType
from grc_services.shared.context import ExecutionContext
from grc_services.shared.exceptions import AuthorizationError

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _database_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if url:
        return url
    env_file = _REPO_ROOT / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def database_url() -> str:
    url = _database_url()
    if not url:
        pytest.skip("no TEST_DATABASE_URL/DATABASE_URL configured")
    return url


@pytest.fixture
def org_id() -> str:
    # Unique per test function: `policies`/`regulatory_obligations` are real, shared Postgres
    # tables with no test-side teardown, so a fixed org id would leak coverage-gap state
    # (e.g. a policy inserted by one test) into another test's scan.
    return f"org-pi-p5-{uuid.uuid4().hex}"


@pytest.fixture
def other_org_id() -> str:
    return f"org-pi-p5-{uuid.uuid4().hex}"


@pytest.fixture
def settings(database_url: str, org_id: str, other_org_id: str) -> Settings:
    tokens = {
        "owner-pi": {"user_id": "u-owner-pi", "organization_id": org_id, "roles": ["owner"]},
        "viewer-pi": {"user_id": "u-viewer-pi", "organization_id": org_id, "roles": ["viewer"]},
        "owner-other-org": {
            "user_id": "u-owner-other",
            "organization_id": other_org_id,
            "roles": ["owner"],
        },
    }
    return Settings(
        app_env="testing",
        llm_provider="fake",
        store_backend="memory",
        auth_seed_dev_principal=False,
        api_auth_tokens=json.dumps(tokens),
        database_url=database_url,
        log_json=False,
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture
async def database(database_url: str) -> AsyncIterator[Database]:
    db = await Database.connect(database_url, min_size=1, max_size=2)
    try:
        yield db
    finally:
        await db.close()


@pytest.fixture
async def seeded_obligation(database: Database) -> dict[str, str]:
    """One confirmed obligation, with its source document, unique to this test run."""
    unique = uuid.uuid4().hex
    raw_documents = RegulatoryRawDocumentRepository(database)
    obligations = RegulatoryObligationRepository(database)

    document = await raw_documents.upsert(
        id=f"doc-{unique}",
        source_id=f"source-{unique}",
        url=f"https://example.gov/{unique}",
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        content_hash=f"hash-{unique}",
        raw_text="Entities shall encrypt data at rest and log every access attempt.",
    )
    obligation = await obligations.upsert(
        id=f"ob-{unique}",
        raw_document_id=document.id,
        obligation_text="Entities shall encrypt data at rest.",
        obligation_type="requirement",
        control_domain="data_protection",
        suggested_policy_title="Encryption Policy",
        severity="high",
        confidence=0.9,
        source_char_start=0,
        source_char_end=32,
        version_hash=f"vhash-{unique}",
        classification_status="confirmed",
    )
    return {"source_id": document.source_id, "obligation_id": obligation.id}


@pytest.fixture
async def seeded_policy(database: Database, org_id: str) -> str:
    """A minimal, incomplete draft policy for ``org_id`` — deliberately thin so Policy
    Analyst's completeness check has something to find."""
    policies = PolicyRepository(database)
    record = await policies.insert_draft(
        tenant_id=org_id,
        title="Access Control Policy",
        summary="A short policy.",
        body="This policy exists.",
        owner_name="TBD",
        control_ids=(),
        created_by_user_id="u-owner-pi",
        created_by_name="Test Owner",
        generated_by_tool="test-fixture",
        generation_metadata={},
    )
    return record.id


async def test_list_obligations_returns_confirmed_obligation_with_citation(
    client: httpx.AsyncClient, seeded_obligation: dict[str, str]
) -> None:
    response = await client.get(
        "/api/v1/policy-intelligence/obligations",
        params={"control_domain": "data_protection"},
        headers=auth("owner-pi"),
    )
    assert response.status_code == 200
    obligations = response.json()["obligations"]
    matches = [o for o in obligations if o["obligation_id"] == seeded_obligation["obligation_id"]]
    assert len(matches) == 1
    assert matches[0]["citation"] == (
        f"{seeded_obligation['source_id']}#{seeded_obligation['obligation_id']}"
    )


async def test_list_obligations_filters_by_control_domain(
    client: httpx.AsyncClient, seeded_obligation: dict[str, str]
) -> None:
    response = await client.get(
        "/api/v1/policy-intelligence/obligations",
        params={"control_domain": "a-domain-nothing-matches"},
        headers=auth("owner-pi"),
    )
    assert response.status_code == 200
    ids = {o["obligation_id"] for o in response.json()["obligations"]}
    assert seeded_obligation["obligation_id"] not in ids


async def test_coverage_gap_scan_reports_unmapped_obligation_with_no_policies(
    client: httpx.AsyncClient, seeded_obligation: dict[str, str]
) -> None:
    response = await client.get(
        "/api/v1/policy-intelligence/coverage-gaps",
        params={"control_domain": "data_protection"},
        headers=auth("owner-pi"),
    )
    assert response.status_code == 200
    body = response.json()
    findings = {f["obligation_id"]: f for f in body["findings"]}
    finding = findings[seeded_obligation["obligation_id"]]
    assert finding["gap_category"] == "unmapped_regulatory_obligation"
    assert finding["matched_policy_id"] is None
    assert finding["citation"] == (
        f"{seeded_obligation['source_id']}#{seeded_obligation['obligation_id']}"
    )


async def test_quality_review_reports_findings_for_a_thin_policy(
    client: httpx.AsyncClient, seeded_policy: str
) -> None:
    response = await client.get(
        f"/api/v1/policy-intelligence/policies/{seeded_policy}/quality-review",
        headers=auth("owner-pi"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["policy_id"] == seeded_policy
    # A one-line body with a placeholder owner is missing most required sections.
    assert len(body["findings"]) > 0
    assert all(f["citation"] for f in body["findings"])


async def test_quality_review_unknown_policy_is_404_problem(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/api/v1/policy-intelligence/policies/does-not-exist/quality-review",
        headers=auth("owner-pi"),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "not_found"


async def test_quality_review_is_tenant_isolated(
    client: httpx.AsyncClient, seeded_policy: str
) -> None:
    """A policy created for one tenant is invisible to another — the same tenant scoping
    ``PolicyRepository.get`` already enforces (CLAUDE.md §20)."""
    response = await client.get(
        f"/api/v1/policy-intelligence/policies/{seeded_policy}/quality-review",
        headers=auth("owner-other-org"),
    )
    assert response.status_code == 404


async def test_policy_intelligence_endpoints_require_authentication(
    client: httpx.AsyncClient,
) -> None:
    obligations = await client.get("/api/v1/policy-intelligence/obligations")
    coverage = await client.get("/api/v1/policy-intelligence/coverage-gaps")
    review = await client.get("/api/v1/policy-intelligence/policies/any-id/quality-review")

    assert obligations.status_code == 401
    assert coverage.status_code == 401
    assert review.status_code == 401


class _DenyEverythingAuthz(AuthorizationService):
    """Proves the router's ``authz.ensure_can`` gate is real, not a no-op — every currently
    defined ``UserRole`` already has POLICY read access (ADR-0022), so a genuine RBAC denial
    can't be produced with real roles alone."""

    async def can(
        self,
        context: ExecutionContext,
        action: Action,
        resource_type: ResourceType,
        resource_id: str | None = None,
    ) -> bool:
        return False

    async def ensure_can(
        self,
        context: ExecutionContext,
        action: Action,
        resource_type: ResourceType,
        resource_id: str | None = None,
    ) -> None:
        raise AuthorizationError(f"denied: {action.value} {resource_type.value}")


async def test_policy_intelligence_endpoints_honor_the_authorization_gate(
    settings: Settings,
) -> None:
    app = create_app(settings)
    app.dependency_overrides[get_authz] = lambda: _DenyEverythingAuthz()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/policy-intelligence/obligations", headers=auth("owner-pi")
        )
    assert response.status_code == 403
    assert response.json()["code"] == "authorization_error"
