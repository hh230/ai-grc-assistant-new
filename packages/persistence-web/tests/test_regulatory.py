"""Integration tests for RegulatoryRawDocumentRepository / RegulatoryObligationRepository
against apps/web's live `regulatory_raw_documents` / `regulatory_obligations` tables —
storage and idempotency for the Regulatory Intelligence pipeline (PI-P1, ADR-0018)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from grc_persistence_web import (
    Database,
    RegulatoryObligationRepository,
    RegulatoryRawDocumentRepository,
)


async def test_raw_document_upsert_round_trips_and_is_idempotent(database: Database) -> None:
    repository = RegulatoryRawDocumentRepository(database)
    content_hash = f"hash-{uuid.uuid4()}"
    try:
        first = await repository.upsert(
            id=str(uuid.uuid4()),
            source_id="nca-ecc",
            url="https://example.gov/nca-ecc",
            fetched_at=datetime.now(timezone.utc),
            content_hash=content_hash,
            raw_text="1. Entities shall encrypt data at rest.",
        )
        assert first.source_id == "nca-ecc"
        assert first.raw_text == "1. Entities shall encrypt data at rest."

        # Re-fetching the same (unchanged) content is idempotent: same id, no duplicate row,
        # even though this second call passes a brand-new id/url/fetched_at.
        second = await repository.upsert(
            id=str(uuid.uuid4()),
            source_id="nca-ecc",
            url="https://example.gov/nca-ecc?v=2",
            fetched_at=datetime.now(timezone.utc),
            content_hash=content_hash,
            raw_text="1. Entities shall encrypt data at rest.",
        )
        assert second.id == first.id
        assert second.url == first.url

        fetched = await repository.get(first.id)
        assert fetched is not None
        assert fetched.content_hash == content_hash

        by_hash = await repository.get_by_content_hash(content_hash)
        assert by_hash is not None
        assert by_hash.id == first.id
    finally:
        async with database.pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM regulatory_raw_documents WHERE content_hash = $1", content_hash
            )


async def test_get_returns_none_for_unknown_raw_document(database: Database) -> None:
    repository = RegulatoryRawDocumentRepository(database)
    assert await repository.get(str(uuid.uuid4())) is None
    assert await repository.get_by_content_hash(f"missing-{uuid.uuid4()}") is None


async def test_obligation_upsert_round_trips_and_is_idempotent(database: Database) -> None:
    documents = RegulatoryRawDocumentRepository(database)
    obligations = RegulatoryObligationRepository(database)
    content_hash = f"hash-{uuid.uuid4()}"
    version_hash = f"version-{uuid.uuid4()}"
    try:
        document = await documents.upsert(
            id=str(uuid.uuid4()),
            source_id="nca-ecc",
            url="https://example.gov/nca-ecc",
            fetched_at=datetime.now(timezone.utc),
            content_hash=content_hash,
            raw_text="1. Entities shall encrypt data at rest.",
        )

        first = await obligations.upsert(
            id=str(uuid.uuid4()),
            raw_document_id=document.id,
            obligation_text="Entities shall encrypt data at rest.",
            obligation_type="requirement",
            control_domain="data_protection",
            suggested_policy_title="Data Encryption Policy",
            severity="high",
            confidence=0.9,
            source_char_start=3,
            source_char_end=41,
            version_hash=version_hash,
            classifier_model="gpt-4o-mini",
            prompt_version="classify_regulatory_obligation.v1",
        )
        assert first.classification_status == "pending_review"  # column default
        assert first.raw_document_id == document.id

        # Re-running the pipeline over the same span/text is idempotent on version_hash.
        second = await obligations.upsert(
            id=str(uuid.uuid4()),
            raw_document_id=document.id,
            obligation_text="Entities shall encrypt data at rest.",
            obligation_type="requirement",
            control_domain="data_protection",
            suggested_policy_title="Data Encryption Policy",
            severity="high",
            confidence=0.9,
            source_char_start=3,
            source_char_end=41,
            version_hash=version_hash,
        )
        assert second.id == first.id

        fetched = await obligations.get(first.id)
        assert fetched is not None
        assert fetched.obligation_type == "requirement"

        by_hash = await obligations.get_by_version_hash(version_hash)
        assert by_hash is not None
        assert by_hash.id == first.id

        by_document = await obligations.list_by_raw_document(document.id)
        assert [record.id for record in by_document] == [first.id]

        pending = await obligations.list_by_status("pending_review")
        assert first.id in [record.id for record in pending]
    finally:
        async with database.pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM regulatory_raw_documents WHERE content_hash = $1", content_hash
            )


async def test_get_returns_none_for_unknown_obligation(database: Database) -> None:
    repository = RegulatoryObligationRepository(database)
    assert await repository.get(str(uuid.uuid4())) is None
    assert await repository.get_by_version_hash(f"missing-{uuid.uuid4()}") is None


async def test_get_latest_content_hash_supports_crawler_change_detection(
    database: Database,
) -> None:
    """PI-P2: each new version of a document is its own row (content_hash is unique), so
    'latest by URL' must return the most recently stored hash, not just any matching row."""
    repository = RegulatoryRawDocumentRepository(database)
    source_id = f"src-{uuid.uuid4()}"
    url = "https://example.gov/circular-1"
    try:
        assert await repository.get_latest_content_hash(source_id, url) is None

        first_hash = f"hash-{uuid.uuid4()}"
        await repository.upsert(
            id=str(uuid.uuid4()),
            source_id=source_id,
            url=url,
            fetched_at=datetime.now(timezone.utc),
            content_hash=first_hash,
            raw_text="1. Entities shall encrypt data at rest.",
        )
        assert await repository.get_latest_content_hash(source_id, url) == first_hash

        second_hash = f"hash-{uuid.uuid4()}"
        await repository.upsert(
            id=str(uuid.uuid4()),
            source_id=source_id,
            url=url,
            fetched_at=datetime.now(timezone.utc),
            content_hash=second_hash,
            raw_text="1. Entities shall encrypt data at rest and in transit.",
        )
        assert await repository.get_latest_content_hash(source_id, url) == second_hash
    finally:
        async with database.pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM regulatory_raw_documents WHERE source_id = $1", source_id
            )


async def test_list_latest_urls_by_source_supports_removed_document_detection(
    database: Database,
) -> None:
    repository = RegulatoryRawDocumentRepository(database)
    source_id = f"src-{uuid.uuid4()}"
    try:
        assert await repository.list_latest_urls_by_source(source_id) == []

        await repository.upsert(
            id=str(uuid.uuid4()),
            source_id=source_id,
            url="https://example.gov/circular-1",
            fetched_at=datetime.now(timezone.utc),
            content_hash=f"hash-{uuid.uuid4()}",
            raw_text="1. Entities shall encrypt data at rest.",
        )
        await repository.upsert(
            id=str(uuid.uuid4()),
            source_id=source_id,
            url="https://example.gov/circular-2",
            fetched_at=datetime.now(timezone.utc),
            content_hash=f"hash-{uuid.uuid4()}",
            raw_text="2. Entities shall log every access attempt.",
        )

        urls = await repository.list_latest_urls_by_source(source_id)
        assert set(urls) == {
            "https://example.gov/circular-1",
            "https://example.gov/circular-2",
        }
    finally:
        async with database.pool.acquire() as connection:
            await connection.execute(
                "DELETE FROM regulatory_raw_documents WHERE source_id = $1", source_id
            )
