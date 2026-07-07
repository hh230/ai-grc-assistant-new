"""Read/write access to apps/web's `regulation_sources` / `regulation_source_versions` /
`regulation_documents` / `regulation_sections` tables — the first production Postgres
persistence for `grc_domain.knowledge`'s `KnowledgeSource -> KnowledgeSourceVersion ->
KnowledgeDocument -> KnowledgeSection` model (Knowledge Intelligence KI-P6, ADR-0030).

Platform-scope (no `tenant_id`), like `knowledge_items`: Saudi regulations are shared
reference data every tenant draws from. Deliberately bypasses `packages/persistence`'s
SQLAlchemy UnitOfWork/outbox (the M6 Extraction Engine's own intended
`KnowledgeIngestionPort` path, blocked pending ADL-0008) — the same direct-asyncpg,
hand-written-SQL pattern every prior Knowledge Intelligence phase already uses.

Every fetched version starts `status = 'in_review'` ("pending_review") and stays there until
an explicit admin decision (`approve`/`reject`, KI-P7) — nothing here ever sets `approved`,
`published`, or attaches an `approved_by` on its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from .pool import Database

_SOURCE_COLUMNS = """
  id, short_code, title_ar, title_en, authority, jurisdiction, knowledge_domain,
  document_type, boe_source_url, created_at, updated_at
"""
_VERSION_COLUMNS = """
  id, source_id, version_label, status, official_citation, effective_start, effective_end,
  publication_date, change_summary_ar, change_summary_en, content_hash, approved_by,
  approved_at, created_at, updated_at
"""
_DOCUMENT_COLUMNS = """
  id, version_id, language, document_format, source_url, content_hash, byte_size, created_at
"""
_SECTION_COLUMNS = """
  id, document_id, section_type, code, path, title_ar, title_en, text_ar, text_en, position,
  parent_section_id, amendment_note_ar, amendment_note_en, created_at, updated_at
"""


@dataclass(frozen=True)
class RegulationSourceRecord:
    id: str
    short_code: str
    title_ar: str
    title_en: str | None
    authority: str
    jurisdiction: str
    knowledge_domain: str
    document_type: str
    boe_source_url: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RegulationSourceVersionRecord:
    id: str
    source_id: str
    version_label: str
    status: str
    official_citation: str | None
    effective_start: date | None
    effective_end: date | None
    publication_date: date | None
    change_summary_ar: str | None
    change_summary_en: str | None
    content_hash: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RegulationDocumentRecord:
    id: str
    version_id: str
    language: str
    document_format: str
    source_url: str
    content_hash: str
    byte_size: int | None
    created_at: datetime


@dataclass(frozen=True)
class RegulationSectionRecord:
    id: str
    document_id: str
    section_type: str
    code: str
    path: list[str]
    title_ar: str | None
    title_en: str | None
    text_ar: str | None
    text_en: str | None
    position: int
    parent_section_id: str | None
    amendment_note_ar: str | None
    amendment_note_en: str | None
    created_at: datetime
    updated_at: datetime


def _to_source_record(row: object) -> RegulationSourceRecord:
    return RegulationSourceRecord(
        id=row["id"],  # type: ignore[index]
        short_code=row["short_code"],  # type: ignore[index]
        title_ar=row["title_ar"],  # type: ignore[index]
        title_en=row["title_en"],  # type: ignore[index]
        authority=row["authority"],  # type: ignore[index]
        jurisdiction=row["jurisdiction"],  # type: ignore[index]
        knowledge_domain=row["knowledge_domain"],  # type: ignore[index]
        document_type=row["document_type"],  # type: ignore[index]
        boe_source_url=row["boe_source_url"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
        updated_at=row["updated_at"],  # type: ignore[index]
    )


def _to_version_record(row: object) -> RegulationSourceVersionRecord:
    return RegulationSourceVersionRecord(
        id=row["id"],  # type: ignore[index]
        source_id=row["source_id"],  # type: ignore[index]
        version_label=row["version_label"],  # type: ignore[index]
        status=row["status"],  # type: ignore[index]
        official_citation=row["official_citation"],  # type: ignore[index]
        effective_start=row["effective_start"],  # type: ignore[index]
        effective_end=row["effective_end"],  # type: ignore[index]
        publication_date=row["publication_date"],  # type: ignore[index]
        change_summary_ar=row["change_summary_ar"],  # type: ignore[index]
        change_summary_en=row["change_summary_en"],  # type: ignore[index]
        content_hash=row["content_hash"],  # type: ignore[index]
        approved_by=row["approved_by"],  # type: ignore[index]
        approved_at=row["approved_at"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
        updated_at=row["updated_at"],  # type: ignore[index]
    )


def _to_document_record(row: object) -> RegulationDocumentRecord:
    return RegulationDocumentRecord(
        id=row["id"],  # type: ignore[index]
        version_id=row["version_id"],  # type: ignore[index]
        language=row["language"],  # type: ignore[index]
        document_format=row["document_format"],  # type: ignore[index]
        source_url=row["source_url"],  # type: ignore[index]
        content_hash=row["content_hash"],  # type: ignore[index]
        byte_size=row["byte_size"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
    )


def _to_section_record(row: object) -> RegulationSectionRecord:
    return RegulationSectionRecord(
        id=row["id"],  # type: ignore[index]
        document_id=row["document_id"],  # type: ignore[index]
        section_type=row["section_type"],  # type: ignore[index]
        code=row["code"],  # type: ignore[index]
        path=list(row["path"]),  # type: ignore[index]
        title_ar=row["title_ar"],  # type: ignore[index]
        title_en=row["title_en"],  # type: ignore[index]
        text_ar=row["text_ar"],  # type: ignore[index]
        text_en=row["text_en"],  # type: ignore[index]
        position=row["position"],  # type: ignore[index]
        parent_section_id=row["parent_section_id"],  # type: ignore[index]
        amendment_note_ar=row["amendment_note_ar"],  # type: ignore[index]
        amendment_note_en=row["amendment_note_en"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
        updated_at=row["updated_at"],  # type: ignore[index]
    )


class RegulationSourceRepository:
    """A regulation's stable identity (its law name/authority/jurisdiction) — created once,
    never overwritten by re-ingestion (that's what versions are for)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_by_short_code(self, short_code: str) -> RegulationSourceRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_SOURCE_COLUMNS} FROM regulation_sources WHERE short_code = $1",
                short_code,
            )
        return _to_source_record(row) if row is not None else None

    async def upsert(
        self,
        *,
        id: str,
        short_code: str,
        title_ar: str,
        authority: str,
        jurisdiction: str,
        knowledge_domain: str,
        document_type: str,
        boe_source_url: str,
        title_en: str | None = None,
    ) -> RegulationSourceRecord:
        """Create-if-absent by `short_code`. A source already on file is returned unchanged —
        its identity fields are set once at discovery; `boe_source_url` drift (the portal
        renaming a page) is a future-work concern, not silently overwritten here."""
        existing = await self.get_by_short_code(short_code)
        if existing is not None:
            return existing
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                INSERT INTO regulation_sources (
                  id, short_code, title_ar, title_en, authority, jurisdiction,
                  knowledge_domain, document_type, boe_source_url
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING {_SOURCE_COLUMNS}
                """,
                id,
                short_code,
                title_ar,
                title_en,
                authority,
                jurisdiction,
                knowledge_domain,
                document_type,
                boe_source_url,
            )
        assert row is not None  # noqa: S101 - RETURNING always yields the inserted row
        return _to_source_record(row)

    async def get_by_id(self, source_id: str) -> RegulationSourceRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_SOURCE_COLUMNS} FROM regulation_sources WHERE id = $1", source_id
            )
        return _to_source_record(row) if row is not None else None


class RegulationSourceVersionRepository:
    """One row per fetched revision. `upsert_draft` is idempotent on content: re-ingesting
    unchanged content is a no-op; a real change drafts a new `in_review` version, never edits
    a prior one (mirrors `KnowledgeSourceVersion`'s own immutability rule)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_by_id(self, version_id: str) -> RegulationSourceVersionRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_VERSION_COLUMNS} FROM regulation_source_versions WHERE id = $1",
                version_id,
            )
        return _to_version_record(row) if row is not None else None

    async def get_latest_for_source(self, source_id: str) -> RegulationSourceVersionRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                SELECT {_VERSION_COLUMNS} FROM regulation_source_versions
                WHERE source_id = $1 ORDER BY created_at DESC LIMIT 1
                """,
                source_id,
            )
        return _to_version_record(row) if row is not None else None

    async def upsert_draft(
        self,
        *,
        id: str,
        source_id: str,
        version_label: str,
        content_hash: str,
        official_citation: str | None = None,
        effective_start: date | None = None,
        effective_end: date | None = None,
        publication_date: date | None = None,
        change_summary_ar: str | None = None,
        change_summary_en: str | None = None,
    ) -> tuple[RegulationSourceVersionRecord, bool]:
        """Returns ``(record, created)``. ``created`` is ``False`` when the latest version for
        this source already has this exact `content_hash` (a genuine no-op re-fetch)."""
        latest = await self.get_latest_for_source(source_id)
        if latest is not None and latest.content_hash == content_hash:
            return latest, False

        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                INSERT INTO regulation_source_versions (
                  id, source_id, version_label, official_citation, effective_start,
                  effective_end, publication_date, change_summary_ar, change_summary_en,
                  content_hash
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING {_VERSION_COLUMNS}
                """,
                id,
                source_id,
                version_label,
                official_citation,
                effective_start,
                effective_end,
                publication_date,
                change_summary_ar,
                change_summary_en,
                content_hash,
            )
        assert row is not None  # noqa: S101 - RETURNING always yields the inserted row
        return _to_version_record(row), True

    async def list_pending(self, limit: int = 50) -> list[RegulationSourceVersionRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                f"""
                SELECT {_VERSION_COLUMNS} FROM regulation_source_versions
                WHERE status = 'in_review' ORDER BY created_at DESC LIMIT $1
                """,
                limit,
            )
        return [_to_version_record(row) for row in rows]

    async def approve(
        self, version_id: str, *, approved_by: str
    ) -> RegulationSourceVersionRecord | None:
        """KI-P7 seam: an explicit admin decision, never called by the ingestion pipeline
        itself."""
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                UPDATE regulation_source_versions
                SET status = 'approved', approved_by = $2, approved_at = now(), updated_at = now()
                WHERE id = $1 AND status = 'in_review'
                RETURNING {_VERSION_COLUMNS}
                """,
                version_id,
                approved_by,
            )
        return _to_version_record(row) if row is not None else None

    async def reject(self, version_id: str) -> RegulationSourceVersionRecord | None:
        """KI-P7 seam: an explicit admin decision, never called by the ingestion pipeline
        itself."""
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                UPDATE regulation_source_versions
                SET status = 'rejected', updated_at = now()
                WHERE id = $1 AND status = 'in_review'
                RETURNING {_VERSION_COLUMNS}
                """,
                version_id,
            )
        return _to_version_record(row) if row is not None else None


class RegulationDocumentRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def insert(
        self,
        *,
        id: str,
        version_id: str,
        language: str,
        document_format: str,
        source_url: str,
        content_hash: str,
        byte_size: int | None = None,
    ) -> RegulationDocumentRecord:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                INSERT INTO regulation_documents (
                  id, version_id, language, document_format, source_url, content_hash,
                  byte_size
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING {_DOCUMENT_COLUMNS}
                """,
                id,
                version_id,
                language,
                document_format,
                source_url,
                content_hash,
                byte_size,
            )
        assert row is not None  # noqa: S101 - RETURNING always yields the inserted row
        return _to_document_record(row)

    async def list_for_version(self, version_id: str) -> list[RegulationDocumentRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                f"SELECT {_DOCUMENT_COLUMNS} FROM regulation_documents WHERE version_id = $1",
                version_id,
            )
        return [_to_document_record(row) for row in rows]


@dataclass(frozen=True)
class NewRegulationSection:
    """One section to insert — the write-side shape `bulk_insert` accepts, kept separate from
    `RegulationSectionRecord` (the read-side shape, which also carries `id`/timestamps)."""

    id: str
    document_id: str
    section_type: str
    code: str
    path: tuple[str, ...]
    position: int
    title_ar: str | None = None
    title_en: str | None = None
    text_ar: str | None = None
    text_en: str | None = None
    parent_section_id: str | None = None
    amendment_note_ar: str | None = None
    amendment_note_en: str | None = None


@dataclass(frozen=True)
class SectionEmbeddingCandidate:
    """One section awaiting embedding (KI-P7, ADR-0031) — just enough to call an
    ``EmbeddingModel`` with, deliberately narrower than ``RegulationSectionRecord``."""

    id: str
    text_ar: str


class NewSectionLike(Protocol):
    """The write-side shape ``RegulationSectionRepository.bulk_insert`` actually reads off each
    section, declared structurally (matching ``NewRegulationSection``, a frozen dataclass whose
    fields satisfy these read-only properties) so a caller in another adapters package — e.g.
    ``grc_regulation_ingestion_adapters``'s own mirrored ``NewSectionLike`` Protocol — never
    needs to import this package's concrete dataclass just to build sections for storage."""

    @property
    def id(self) -> str: ...
    @property
    def document_id(self) -> str: ...
    @property
    def section_type(self) -> str: ...
    @property
    def code(self) -> str: ...
    @property
    def path(self) -> tuple[str, ...]: ...
    @property
    def position(self) -> int: ...
    @property
    def title_ar(self) -> str | None: ...
    @property
    def title_en(self) -> str | None: ...
    @property
    def text_ar(self) -> str | None: ...
    @property
    def text_en(self) -> str | None: ...
    @property
    def parent_section_id(self) -> str | None: ...
    @property
    def amendment_note_ar(self) -> str | None: ...
    @property
    def amendment_note_en(self) -> str | None: ...


class RegulationSectionRepository:
    """One row per legal unit (article/chapter/clause/...) — never split across rows."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def bulk_insert(
        self, sections: Sequence[NewSectionLike]
    ) -> list[RegulationSectionRecord]:
        if not sections:
            return []
        async with self._database.pool.acquire() as connection, connection.transaction():
            rows = [
                await connection.fetchrow(
                    f"""
                    INSERT INTO regulation_sections (
                      id, document_id, section_type, code, path, title_ar, title_en, text_ar,
                      text_en, position, parent_section_id, amendment_note_ar,
                      amendment_note_en
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    RETURNING {_SECTION_COLUMNS}
                    """,
                    section.id,
                    section.document_id,
                    section.section_type,
                    section.code,
                    list(section.path),
                    section.title_ar,
                    section.title_en,
                    section.text_ar,
                    section.text_en,
                    section.position,
                    section.parent_section_id,
                    section.amendment_note_ar,
                    section.amendment_note_en,
                )
                for section in sections
            ]
        return [_to_section_record(row) for row in rows if row is not None]

    async def list_for_document(self, document_id: str) -> list[RegulationSectionRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                f"""
                SELECT {_SECTION_COLUMNS} FROM regulation_sections
                WHERE document_id = $1 ORDER BY position
                """,
                document_id,
            )
        return [_to_section_record(row) for row in rows]

    async def list_needing_embedding(self, document_id: str) -> list[SectionEmbeddingCandidate]:
        """Sections with real article text but no embedding yet — the exact set a KI-P7
        approval needs to embed. Excludes chapter headings (no `text_ar` of their own) and,
        idempotently, anything already embedded by a prior attempt (so a retry after a partial
        failure never re-embeds or double-charges for a section that already succeeded)."""
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT id, text_ar FROM regulation_sections
                WHERE document_id = $1 AND text_ar IS NOT NULL AND embedding IS NULL
                ORDER BY position
                """,
                document_id,
            )
        return [SectionEmbeddingCandidate(id=row["id"], text_ar=row["text_ar"]) for row in rows]

    async def set_embedding(
        self, section_id: str, *, embedding: Sequence[float], model: str
    ) -> None:
        """Writes one section's embedding vector. asyncpg has no built-in pgvector codec, so
        the vector travels as its pgvector text literal (``'[0.1,0.2,...]'``) and is cast with
        ``$2::vector`` — the same approach apps/web's TypeScript side already accepts for this
        column shape (0005_document_chunks.sql), just from the Python side for the first time.
        """
        vector_literal = "[" + ",".join(repr(value) for value in embedding) + "]"
        async with self._database.pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE regulation_sections
                SET embedding = $2::vector, embedding_model = $3, embedded_at = now()
                WHERE id = $1
                """,
                section_id,
                vector_literal,
                model,
            )
