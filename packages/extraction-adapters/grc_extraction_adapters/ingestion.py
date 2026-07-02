"""A reference in-memory ingestion adapter (implements ``KnowledgeIngestionPort``).

Persists an ``ExtractionResult`` to memory and assigns deterministic ids, giving the engine a
complete, runnable persistence seam without a database. It also implements idempotency: a document
whose content hash was already ingested is found by ``find_existing`` and not reprocessed.

This is the **reference** ingestion adapter — useful for previews, dry-runs, and tests, and as the
contract example for the production adapter. The production adapter persists atomically through the
Knowledge Database's Unit of Work + transactional outbox (CLAUDE.md §12) and lives in the
persistence layer; it is pending the M5 knowledge-persistence re-alignment (see PROJECT_STATE §0).
"""
from __future__ import annotations

from grc_domain.knowledge import ContentHash, KnowledgeScope
from grc_domain.shared.identifiers import KnowledgeObjectId, KnowledgeRelationshipId
from grc_extraction import ExtractionResult, IngestionResult, KnowledgeIngestionPort


class InMemoryKnowledgeIngestion(KnowledgeIngestionPort):
    """Stores extraction results in memory, keyed for idempotent re-ingestion."""

    def __init__(self) -> None:
        self._by_content: dict[tuple[str, str], IngestionResult] = {}
        self.persisted: list[ExtractionResult] = []

    async def find_existing(
        self, scope: KnowledgeScope, content_hash: ContentHash
    ) -> IngestionResult | None:
        return self._by_content.get(_key(content_hash))

    async def persist_result(self, result: ExtractionResult) -> IngestionResult:
        self.persisted.append(result)
        object_ids = tuple(
            KnowledgeObjectId(f"ko-{result.run_id}-{index}") for index in range(len(result.objects))
        )
        relationship_ids = tuple(
            KnowledgeRelationshipId(f"kr-{result.run_id}-{index}")
            for index in range(len(result.relationships))
        )
        ingestion = IngestionResult(
            object_ids=object_ids,
            relationship_ids=relationship_ids,
            version_id=result.version_id,
        )
        for document in result.documents:
            self._by_content[_key(document.content_hash)] = ingestion
        return ingestion


def _key(content_hash: ContentHash) -> tuple[str, str]:
    return (content_hash.algorithm, content_hash.value)
