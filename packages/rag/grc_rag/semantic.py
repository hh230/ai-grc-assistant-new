"""Semantic (vector) search over knowledge objects — the embedding half of hybrid retrieval.

Uses an injected ``EmbeddingModel`` (provider-agnostic) to embed objects and queries, and ranks by
cosine similarity in an in-memory store. This completes the vector side of CLAUDE.md §12.2; in
production the in-memory store is swapped for pgvector behind the same shape. Tenant-isolated.
"""
from __future__ import annotations

from dataclasses import dataclass

from grc_domain.knowledge import KnowledgeObject, KnowledgeObjectType, KnowledgeScope
from grc_domain.shared.identifiers import KnowledgeObjectId
from grc_llm import EmbeddingModel

from .exceptions import CrossScopeError


@dataclass(frozen=True)
class SemanticHit:
    """A semantic match: the object and its cosine similarity to the query."""

    object_id: KnowledgeObjectId
    object_type: KnowledgeObjectType
    similarity: float


@dataclass(frozen=True)
class _Entry:
    object_id: KnowledgeObjectId
    object_type: KnowledgeObjectType
    vector: tuple[float, ...]


class SemanticSearchIndex:
    """Embeds knowledge objects and answers nearest-neighbour queries by cosine similarity."""

    def __init__(self, scope: KnowledgeScope, embedder: EmbeddingModel) -> None:
        self._scope = scope
        self._embedder = embedder
        self._entries: list[_Entry] = []

    @property
    def size(self) -> int:
        return len(self._entries)

    async def index(self, knowledge_object: KnowledgeObject) -> None:
        if knowledge_object.scope != self._scope:
            raise CrossScopeError(f"object {knowledge_object.id} is outside the index's scope")
        text = knowledge_object.normalized_statement or knowledge_object.verbatim_text
        result = await self._embedder.embed([text])
        self._entries.append(
            _Entry(
                object_id=knowledge_object.id,
                object_type=knowledge_object.object_type,
                vector=result.vectors[0],
            )
        )

    async def search(
        self,
        query: str,
        *,
        object_type: KnowledgeObjectType | None = None,
        limit: int = 5,
    ) -> tuple[SemanticHit, ...]:
        if limit <= 0:
            raise ValueError("limit must be > 0")
        if not self._entries:
            return ()
        query_vector = (await self._embedder.embed([query])).vectors[0]
        hits = [
            SemanticHit(
                object_id=entry.object_id,
                object_type=entry.object_type,
                similarity=_cosine(query_vector, entry.vector),
            )
            for entry in self._entries
            if object_type is None or entry.object_type is object_type
        ]
        hits.sort(key=lambda hit: (-hit.similarity, str(hit.object_id)))
        return tuple(hits[:limit])


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("cosine similarity requires equal-length vectors")
    return sum(a * b for a, b in zip(left, right, strict=True))
