"""Integration tests for the Regulation Review router (KI-P7, ADR-0031): pending listing,
version detail, approve (incl. embedding generation via the fake embedding model), reject, and
RBAC (owner/admin can decide, auditor can read but never decide, viewer forbidden everywhere),
driven through the real ASGI app against apps/web's live Postgres schema.

Needs a real database with apps/web's migrations applied (same convention as
``test_knowledge_worker.py``): point ``TEST_DATABASE_URL`` (or ``DATABASE_URL``) at one, or
these tests skip cleanly.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from grc_api.app import create_app
from grc_api.settings import Settings
from grc_persistence_web import (
    Database,
    NewRegulationSection,
    RegulationDocumentRepository,
    RegulationSectionRepository,
    RegulationSourceRepository,
    RegulationSourceVersionRepository,
)

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
def settings(database_url: str) -> Settings:
    tokens = {
        "admin-rr": {"user_id": "u-admin-rr", "organization_id": "org-rr", "roles": ["admin"]},
        "owner-rr": {"user_id": "u-owner-rr", "organization_id": "org-rr", "roles": ["owner"]},
        "viewer-rr": {"user_id": "u-viewer-rr", "organization_id": "org-rr", "roles": ["viewer"]},
        "auditor-rr": {
            "user_id": "u-auditor-rr",
            "organization_id": "org-rr",
            "roles": ["auditor"],
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


async def _cleanup_source(database: Database, source_id: str) -> None:
    async with database.pool.acquire() as connection:
        await connection.execute(
            """
            DELETE FROM regulation_sections WHERE document_id IN (
              SELECT id FROM regulation_documents WHERE version_id IN (
                SELECT id FROM regulation_source_versions WHERE source_id = $1
              )
            )
            """,
            source_id,
        )
        await connection.execute(
            "DELETE FROM regulation_documents WHERE version_id IN "
            "(SELECT id FROM regulation_source_versions WHERE source_id = $1)",
            source_id,
        )
        await connection.execute(
            "DELETE FROM regulation_source_versions WHERE source_id = $1", source_id
        )
        await connection.execute("DELETE FROM regulation_sources WHERE id = $1", source_id)


async def _make_pending_version(database: Database, *, content_hash: str) -> tuple[str, str]:
    """Builds one real source -> in_review version -> document -> (chapter + article) section
    tree, matching persistence-web's own `test_regulations.py` fixture convention. Returns
    ``(source_id, version_id)``."""
    source_id = str(uuid.uuid4())
    await RegulationSourceRepository(database).upsert(
        id=source_id,
        short_code=f"test-review-{uuid.uuid4()}",
        title_ar="نظام تجريبي للمراجعة",
        authority="test authority",
        jurisdiction="SA",
        knowledge_domain="legal_regulatory",
        document_type="law",
        boe_source_url="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/review-test/1",
    )
    version, _ = await RegulationSourceVersionRepository(database).upsert_draft(
        id=str(uuid.uuid4()),
        source_id=source_id,
        version_label="v1",
        content_hash=content_hash,
    )
    document = await RegulationDocumentRepository(database).insert(
        id=str(uuid.uuid4()),
        version_id=version.id,
        language="ar",
        document_format="html",
        source_url="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/review-test/1",
        content_hash=f"doc-{content_hash}",
    )
    chapter_id = str(uuid.uuid4())
    article_id = str(uuid.uuid4())
    await RegulationSectionRepository(database).bulk_insert(
        (
            NewRegulationSection(
                id=chapter_id,
                document_id=document.id,
                section_type="chapter",
                code="الباب الأول",
                path=(),
                position=0,
                title_ar="الباب الأول",
            ),
            NewRegulationSection(
                id=article_id,
                document_id=document.id,
                section_type="article",
                code="المادة الأولى",
                path=("الباب الأول",),
                position=1,
                parent_section_id=chapter_id,
                text_ar="نص المادة الأولى للمراجعة.",
            ),
        )
    )
    return source_id, version.id


async def test_pending_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/regulation-review/pending")
    assert response.status_code == 401


async def test_viewer_is_forbidden_from_every_route(
    client: httpx.AsyncClient, database: Database
) -> None:
    source_id, version_id = await _make_pending_version(database, content_hash="viewer-forbidden")
    try:
        pending_response = await client.get(
            "/api/v1/regulation-review/pending", headers=auth("viewer-rr")
        )
        detail_response = await client.get(
            f"/api/v1/regulation-review/{version_id}", headers=auth("viewer-rr")
        )
        approve_response = await client.post(
            f"/api/v1/regulation-review/{version_id}/approve", headers=auth("viewer-rr")
        )
        assert pending_response.status_code == 403
        assert detail_response.status_code == 403
        assert approve_response.status_code == 403
    finally:
        await _cleanup_source(database, source_id)


async def test_auditor_can_read_but_never_decide(
    client: httpx.AsyncClient, database: Database
) -> None:
    source_id, version_id = await _make_pending_version(database, content_hash="auditor-read-only")
    try:
        pending_response = await client.get(
            "/api/v1/regulation-review/pending", headers=auth("auditor-rr")
        )
        detail_response = await client.get(
            f"/api/v1/regulation-review/{version_id}", headers=auth("auditor-rr")
        )
        approve_response = await client.post(
            f"/api/v1/regulation-review/{version_id}/approve", headers=auth("auditor-rr")
        )
        reject_response = await client.post(
            f"/api/v1/regulation-review/{version_id}/reject", headers=auth("auditor-rr")
        )
        assert pending_response.status_code == 200
        assert detail_response.status_code == 200
        assert approve_response.status_code == 403
        assert reject_response.status_code == 403
    finally:
        await _cleanup_source(database, source_id)


async def test_pending_lists_the_version_with_its_source(
    client: httpx.AsyncClient, database: Database
) -> None:
    source_id, version_id = await _make_pending_version(database, content_hash="pending-listing")
    try:
        response = await client.get("/api/v1/regulation-review/pending", headers=auth("admin-rr"))
        assert response.status_code == 200
        entry = next(v for v in response.json() if v["version_id"] == version_id)
        assert entry["status"] == "in_review"
        assert entry["source"]["title_ar"] == "نظام تجريبي للمراجعة"
    finally:
        await _cleanup_source(database, source_id)


async def test_detail_returns_documents_and_sections(
    client: httpx.AsyncClient, database: Database
) -> None:
    source_id, version_id = await _make_pending_version(database, content_hash="detail-view")
    try:
        response = await client.get(
            f"/api/v1/regulation-review/{version_id}", headers=auth("admin-rr")
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["documents"]) == 1
        sections = body["documents"][0]["sections"]
        assert [s["section_type"] for s in sections] == ["chapter", "article"]
        assert sections[1]["text_ar"] == "نص المادة الأولى للمراجعة."
    finally:
        await _cleanup_source(database, source_id)


async def test_detail_404s_for_an_unknown_version(client: httpx.AsyncClient) -> None:
    response = await client.get(
        f"/api/v1/regulation-review/{uuid.uuid4()}", headers=auth("admin-rr")
    )
    assert response.status_code == 404


async def test_approve_marks_approved_and_embeds_the_article_section(
    client: httpx.AsyncClient, database: Database
) -> None:
    source_id, version_id = await _make_pending_version(database, content_hash="approve-flow")
    try:
        response = await client.post(
            f"/api/v1/regulation-review/{version_id}/approve", headers=auth("owner-rr")
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "approved"
        assert body["approved_by"] == "u-owner-rr"
        # One chapter (no text_ar, not a candidate) + one article (text_ar present) were
        # inserted; only the article should have been embedded.
        assert body["sections_embedded"] == 1
        assert body["sections_failed"] == 0

        async with database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT embedding_model, embedded_at FROM regulation_sections "
                "WHERE document_id IN (SELECT id FROM regulation_documents WHERE version_id = $1) "
                "AND section_type = 'article'",
                version_id,
            )
        assert row is not None
        assert row["embedding_model"] == "fake-embed"
        assert row["embedded_at"] is not None

        # A second approve on the now-approved version is a conflict, not a silent no-op.
        second_response = await client.post(
            f"/api/v1/regulation-review/{version_id}/approve", headers=auth("owner-rr")
        )
        assert second_response.status_code == 409
    finally:
        await _cleanup_source(database, source_id)


async def test_reject_marks_rejected(client: httpx.AsyncClient, database: Database) -> None:
    source_id, version_id = await _make_pending_version(database, content_hash="reject-flow")
    try:
        response = await client.post(
            f"/api/v1/regulation-review/{version_id}/reject", headers=auth("admin-rr")
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

        second_response = await client.post(
            f"/api/v1/regulation-review/{version_id}/reject", headers=auth("admin-rr")
        )
        assert second_response.status_code == 409
    finally:
        await _cleanup_source(database, source_id)


async def test_approve_404s_for_an_unknown_version(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/regulation-review/{uuid.uuid4()}/approve", headers=auth("admin-rr")
    )
    assert response.status_code == 404
