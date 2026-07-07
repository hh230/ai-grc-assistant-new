"""Read/write access to apps/web's `knowledge_items` table — the Autonomous Knowledge
Engine's storage stage (Knowledge Intelligence KI-P1, ADR-0025).

Platform-scope (no `tenant_id`): GRC/compliance/legal knowledge is shared reference data every
tenant draws from, exactly like `regulatory_raw_documents`/`regulatory_obligations`. One row
per `question_id` (enforced by a `UNIQUE` constraint): a re-discovery replaces the current
answer and bumps `version` rather than accumulating a full history table. `upsert` is
idempotent on `version_hash` — re-running discovery over an unchanged source excerpt never
duplicates work or resets an already-verified item's status.

KI-P5 follow-up (ADR-0025 §6 revised): a fresh discovery's own `status` is now the caller's
choice between `'discovered'` (the original default) and `'needs_review'` — a real, if
imperfect, grounded answer is still worth keeping rather than discarding, but a
below-confidence-threshold one should not look indistinguishable from a confidently-grounded
one. Moving a `KnowledgeItem` to `'verified'` or `'outdated'` still requires an explicit human
decision via `set_verification_status` — only the *initial* AI-assigned status now has two
possible values instead of one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .pool import Database

_COLUMNS = """
  id, question_id, question, answer, domain, category, applicable_context, source_id,
  source_name, source_type, source_url, jurisdiction, citation, confidence, status,
  last_verified, verified_by, version, version_hash, created_at, updated_at
"""


@dataclass(frozen=True)
class KnowledgeItemRecord:
    id: str
    question_id: str
    question: str
    answer: str
    domain: str
    category: str
    applicable_context: str
    source_id: str
    source_name: str
    source_type: str
    source_url: str
    jurisdiction: str
    citation: str
    confidence: float
    status: str
    last_verified: datetime | None
    verified_by: str | None
    version: int
    version_hash: str
    created_at: datetime
    updated_at: datetime


def _to_record(row: object) -> KnowledgeItemRecord:
    return KnowledgeItemRecord(
        id=row["id"],  # type: ignore[index]
        question_id=row["question_id"],  # type: ignore[index]
        question=row["question"],  # type: ignore[index]
        answer=row["answer"],  # type: ignore[index]
        domain=row["domain"],  # type: ignore[index]
        category=row["category"],  # type: ignore[index]
        applicable_context=row["applicable_context"],  # type: ignore[index]
        source_id=row["source_id"],  # type: ignore[index]
        source_name=row["source_name"],  # type: ignore[index]
        source_type=row["source_type"],  # type: ignore[index]
        source_url=row["source_url"],  # type: ignore[index]
        jurisdiction=row["jurisdiction"],  # type: ignore[index]
        citation=row["citation"],  # type: ignore[index]
        confidence=row["confidence"],  # type: ignore[index]
        status=row["status"],  # type: ignore[index]
        last_verified=row["last_verified"],  # type: ignore[index]
        verified_by=row["verified_by"],  # type: ignore[index]
        version=row["version"],  # type: ignore[index]
        version_hash=row["version_hash"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
        updated_at=row["updated_at"],  # type: ignore[index]
    )


class KnowledgeItemRepository:
    """Stores discovered/verified knowledge produced by
    ``grc_knowledge_intelligence.KnowledgeDiscoveryEngine``, keyed for idempotent upsert on
    ``version_hash`` (``grc_knowledge_intelligence.compute_version_hash``)."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert(
        self,
        *,
        id: str,
        question_id: str,
        question: str,
        answer: str,
        domain: str,
        category: str,
        applicable_context: str,
        source_id: str,
        source_name: str,
        source_type: str,
        source_url: str,
        jurisdiction: str,
        citation: str,
        confidence: float,
        version_hash: str,
        status: str = "discovered",
    ) -> KnowledgeItemRecord:
        """Insert the first discovery for this question, or — if one already exists —
        overwrite it with fresh content and bump ``version`` (resetting to the given
        ``status`` — ``'discovered'`` or ``'needs_review'``, never a human-only status like
        ``'verified'``/``'outdated'`` — and clearing ``last_verified``/``verified_by``, since a
        changed answer needs a human's attention again regardless of confidence). A
        re-discovery whose ``version_hash`` exactly matches the current row is a no-op: it
        returns the existing row unchanged, including its verification status — re-running
        discovery over unchanged source text must never undo a human's prior verification.
        """
        async with self._database.pool.acquire() as connection, connection.transaction():
            existing = await connection.fetchrow(
                f"SELECT {_COLUMNS} FROM knowledge_items WHERE question_id = $1 FOR UPDATE",
                question_id,
            )
            if existing is not None and existing["version_hash"] == version_hash:
                return _to_record(existing)

            if existing is None:
                row = await connection.fetchrow(
                    f"""
                        INSERT INTO knowledge_items (
                          id, question_id, question, answer, domain, category,
                          applicable_context, source_id, source_name, source_type, source_url,
                          jurisdiction, citation, confidence, version_hash, status
                        ) VALUES (
                          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
                        )
                        RETURNING {_COLUMNS}
                        """,
                    id,
                    question_id,
                    question,
                    answer,
                    domain,
                    category,
                    applicable_context,
                    source_id,
                    source_name,
                    source_type,
                    source_url,
                    jurisdiction,
                    citation,
                    confidence,
                    version_hash,
                    status,
                )
            else:
                row = await connection.fetchrow(
                    f"""
                        UPDATE knowledge_items SET
                          question = $2, answer = $3, domain = $4, category = $5,
                          applicable_context = $6, source_id = $7, source_name = $8,
                          source_type = $9, source_url = $10, jurisdiction = $11,
                          citation = $12, confidence = $13, version_hash = $14,
                          status = $15, last_verified = NULL, verified_by = NULL,
                          version = knowledge_items.version + 1, updated_at = now()
                        WHERE question_id = $1
                        RETURNING {_COLUMNS}
                        """,
                    question_id,
                    question,
                    answer,
                    domain,
                    category,
                    applicable_context,
                    source_id,
                    source_name,
                    source_type,
                    source_url,
                    jurisdiction,
                    citation,
                    confidence,
                    version_hash,
                    status,
                )
        assert row is not None  # noqa: S101 - RETURNING always yields the affected row
        return _to_record(row)

    async def get(self, item_id: str) -> KnowledgeItemRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_COLUMNS} FROM knowledge_items WHERE id = $1", item_id
            )
        return _to_record(row) if row is not None else None

    async def get_by_question_id(self, question_id: str) -> KnowledgeItemRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_COLUMNS} FROM knowledge_items WHERE question_id = $1", question_id
            )
        return _to_record(row) if row is not None else None

    async def list_all(self) -> list[KnowledgeItemRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(f"SELECT {_COLUMNS} FROM knowledge_items")
        return [_to_record(row) for row in rows]

    async def list_by_status(self, status: str) -> list[KnowledgeItemRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                f"SELECT {_COLUMNS} FROM knowledge_items WHERE status = $1 "
                "ORDER BY updated_at DESC",
                status,
            )
        return [_to_record(row) for row in rows]

    async def set_verification_status(
        self,
        question_id: str,
        *,
        status: str,
        verified_by: str,
        verified_at: datetime,
    ) -> KnowledgeItemRecord | None:
        """Apply a human's verification decision — the only way a ``KnowledgeItem`` ever
        moves out of ``discovered`` (ADR-0025 §6). Not a Tool: this is a human record-keeping
        action, not an AI capability the Tool Registry needs to mediate, the same reasoning
        that keeps policy publish/approve as `grc_services` commands rather than Tools."""
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                UPDATE knowledge_items
                SET status = $2, verified_by = $3, last_verified = $4, updated_at = now()
                WHERE question_id = $1
                RETURNING {_COLUMNS}
                """,
                question_id,
                status,
                verified_by,
                verified_at,
            )
        return _to_record(row) if row is not None else None
