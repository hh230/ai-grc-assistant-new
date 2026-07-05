"""Read/write access to apps/web's `regulatory_raw_documents` / `regulatory_obligations`
tables — the Regulatory Intelligence storage stage (Policy Intelligence PI-P1, ADR-0018).

Both tables are platform-scope (no `tenant_id`): a regulation is shared reference data every
tenant's Policy Hunter draws from, exactly like the Framework Engine's framework definitions.
Both repositories upsert on their idempotency key (`content_hash` / `version_hash`) so
re-running a connector fetch or the classification pipeline never duplicates rows — the
`RegulatoryIntelligenceEngine` (`grc_regulatory_intelligence`) is designed to be safely
re-run over an unchanged document.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .pool import Database


@dataclass(frozen=True)
class RegulatoryRawDocumentRecord:
    id: str
    source_id: str
    url: str
    fetched_at: datetime
    content_hash: str
    raw_text: str
    created_at: datetime


@dataclass(frozen=True)
class RegulatoryObligationRecord:
    id: str
    raw_document_id: str
    obligation_text: str
    obligation_type: str
    control_domain: str
    suggested_policy_title: str
    severity: str
    confidence: float
    source_char_start: int
    source_char_end: int
    classifier_model: str | None
    prompt_version: str | None
    version_hash: str
    classification_status: str
    created_at: datetime
    updated_at: datetime


def _to_raw_document_record(row: object) -> RegulatoryRawDocumentRecord:
    return RegulatoryRawDocumentRecord(
        id=row["id"],  # type: ignore[index]
        source_id=row["source_id"],  # type: ignore[index]
        url=row["url"],  # type: ignore[index]
        fetched_at=row["fetched_at"],  # type: ignore[index]
        content_hash=row["content_hash"],  # type: ignore[index]
        raw_text=row["raw_text"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
    )


def _to_obligation_record(row: object) -> RegulatoryObligationRecord:
    return RegulatoryObligationRecord(
        id=row["id"],  # type: ignore[index]
        raw_document_id=row["raw_document_id"],  # type: ignore[index]
        obligation_text=row["obligation_text"],  # type: ignore[index]
        obligation_type=row["obligation_type"],  # type: ignore[index]
        control_domain=row["control_domain"],  # type: ignore[index]
        suggested_policy_title=row["suggested_policy_title"],  # type: ignore[index]
        severity=row["severity"],  # type: ignore[index]
        confidence=row["confidence"],  # type: ignore[index]
        source_char_start=row["source_char_start"],  # type: ignore[index]
        source_char_end=row["source_char_end"],  # type: ignore[index]
        classifier_model=row["classifier_model"],  # type: ignore[index]
        prompt_version=row["prompt_version"],  # type: ignore[index]
        version_hash=row["version_hash"],  # type: ignore[index]
        classification_status=row["classification_status"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
        updated_at=row["updated_at"],  # type: ignore[index]
    )


class RegulatoryRawDocumentRepository:
    """Connector fetches land here first — before the engine ever runs, so re-fetching an
    unchanged document is a no-op rather than a duplicate row."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert(
        self,
        *,
        id: str,
        source_id: str,
        url: str,
        fetched_at: datetime,
        content_hash: str,
        raw_text: str,
    ) -> RegulatoryRawDocumentRecord:
        """Insert a fetched document, or return the existing row if this `content_hash` was
        already stored (idempotent — a connector re-fetching unchanged text never
        duplicates)."""
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO regulatory_raw_documents (
                  id, source_id, url, fetched_at, content_hash, raw_text
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (content_hash) DO UPDATE
                  SET content_hash = regulatory_raw_documents.content_hash
                RETURNING id, source_id, url, fetched_at, content_hash, raw_text, created_at
                """,
                id,
                source_id,
                url,
                fetched_at,
                content_hash,
                raw_text,
            )
        assert row is not None  # noqa: S101 - RETURNING always yields the affected row
        return _to_raw_document_record(row)

    async def get(self, document_id: str) -> RegulatoryRawDocumentRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM regulatory_raw_documents WHERE id = $1", document_id
            )
        return _to_raw_document_record(row) if row is not None else None

    async def get_by_content_hash(self, content_hash: str) -> RegulatoryRawDocumentRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM regulatory_raw_documents WHERE content_hash = $1", content_hash
            )
        return _to_raw_document_record(row) if row is not None else None

    async def get_latest_content_hash(self, source_id: str, url: str) -> str | None:
        """The most recently stored content hash for one (source, URL) pair — the crawler's
        change-detection signal (PI-P2, ADR-0019). Each version of a document is its own
        immutable row (content_hash is unique), so this orders by `created_at` rather than
        assuming a single row per URL."""
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT content_hash FROM regulatory_raw_documents "
                "WHERE source_id = $1 AND url = $2 ORDER BY created_at DESC LIMIT 1",
                source_id,
                url,
            )
        return row["content_hash"] if row is not None else None

    async def list_latest_urls_by_source(self, source_id: str) -> list[str]:
        """Every URL ever stored for this source — used to detect removed/unavailable
        documents (a URL previously seen that a fresh crawl no longer discovers)."""
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT DISTINCT url FROM regulatory_raw_documents WHERE source_id = $1",
                source_id,
            )
        return [row["url"] for row in rows]


class RegulatoryObligationRepository:
    """Stores classified obligations produced by `RegulatoryIntelligenceEngine`, keyed for
    idempotent upsert on `version_hash` (`grc_regulatory_intelligence.compute_version_hash`)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert(
        self,
        *,
        id: str,
        raw_document_id: str,
        obligation_text: str,
        obligation_type: str,
        control_domain: str,
        suggested_policy_title: str,
        severity: str,
        confidence: float,
        source_char_start: int,
        source_char_end: int,
        version_hash: str,
        classifier_model: str | None = None,
        prompt_version: str | None = None,
        classification_status: str = "pending_review",
    ) -> RegulatoryObligationRecord:
        """Insert a classified obligation, or return the existing row if this `version_hash`
        was already stored (idempotent — re-running the pipeline over an unchanged document
        never duplicates a row)."""
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO regulatory_obligations (
                  id, raw_document_id, obligation_text, obligation_type, control_domain,
                  suggested_policy_title, severity, confidence, source_char_start,
                  source_char_end, classifier_model, prompt_version, version_hash,
                  classification_status
                ) VALUES (
                  $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                )
                ON CONFLICT (version_hash) DO UPDATE
                  SET version_hash = regulatory_obligations.version_hash
                RETURNING *
                """,
                id,
                raw_document_id,
                obligation_text,
                obligation_type,
                control_domain,
                suggested_policy_title,
                severity,
                confidence,
                source_char_start,
                source_char_end,
                classifier_model,
                prompt_version,
                version_hash,
                classification_status,
            )
        assert row is not None  # noqa: S101 - RETURNING always yields the affected row
        return _to_obligation_record(row)

    async def get(self, obligation_id: str) -> RegulatoryObligationRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM regulatory_obligations WHERE id = $1", obligation_id
            )
        return _to_obligation_record(row) if row is not None else None

    async def get_by_version_hash(self, version_hash: str) -> RegulatoryObligationRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM regulatory_obligations WHERE version_hash = $1", version_hash
            )
        return _to_obligation_record(row) if row is not None else None

    async def list_by_raw_document(self, raw_document_id: str) -> list[RegulatoryObligationRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT * FROM regulatory_obligations WHERE raw_document_id = $1 "
                "ORDER BY source_char_start",
                raw_document_id,
            )
        return [_to_obligation_record(row) for row in rows]

    async def list_by_status(self, classification_status: str) -> list[RegulatoryObligationRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT * FROM regulatory_obligations WHERE classification_status = $1 "
                "ORDER BY created_at DESC",
                classification_status,
            )
        return [_to_obligation_record(row) for row in rows]
