"""Retrieval: turn a query into a bounded, grounded, cited context (Handbook §8 milestone 10).

The retriever indexes knowledge objects, searches them lexically (M9), and assembles the top
results into a ``RetrievalContext`` — each chunk carries its provenance (source version + anchor)
so every downstream claim can cite its origin, and the context respects a size budget. This is the
keyword retrieval path of CLAUDE.md §12.2; a semantic (vector) retriever implements the same shape
behind the retrieval seam once an embedding provider is selected. Single-tenant by construction.
"""
from __future__ import annotations

from dataclasses import dataclass

from grc_domain.knowledge import KnowledgeObject, KnowledgeObjectType, KnowledgeScope
from grc_domain.shared.identifiers import KnowledgeObjectId, KnowledgeSourceVersionId

from .search import LexicalSearchIndex


@dataclass(frozen=True)
class RetrievedChunk:
    """One retrieved knowledge object with its grounding (provenance) and relevance score."""

    object_id: KnowledgeObjectId
    object_type: KnowledgeObjectType
    text: str
    score: float
    source_version_id: KnowledgeSourceVersionId
    anchor: str | None


@dataclass(frozen=True)
class RetrievalContext:
    """The assembled, grounded context for a query — what a generator is constrained to."""

    query: str
    chunks: tuple[RetrievedChunk, ...]

    @property
    def is_empty(self) -> bool:
        return not self.chunks

    def grounded_text(self) -> str:
        """The context block, each chunk tagged with a citation key for grounded generation."""
        return "\n\n".join(f"[{chunk.object_id}] {chunk.text}" for chunk in self.chunks)


class KnowledgeRetriever:
    """Indexes knowledge objects and retrieves a bounded, cited context for a query."""

    def __init__(self, scope: KnowledgeScope) -> None:
        self._scope = scope
        self._index = LexicalSearchIndex(scope)
        self._objects: dict[KnowledgeObjectId, KnowledgeObject] = {}

    @property
    def scope(self) -> KnowledgeScope:
        return self._scope

    @property
    def size(self) -> int:
        return len(self._objects)

    def add(self, knowledge_object: KnowledgeObject) -> None:
        self._index.index(knowledge_object)  # enforces tenant scope
        self._objects[knowledge_object.id] = knowledge_object

    def retrieve(
        self,
        query: str,
        *,
        object_type: KnowledgeObjectType | None = None,
        top_k: int = 5,
        max_total_chars: int = 2000,
    ) -> RetrievalContext:
        if top_k <= 0:
            raise ValueError("top_k must be > 0")
        if max_total_chars <= 0:
            raise ValueError("max_total_chars must be > 0")
        hits = self._index.search(query, object_type=object_type, limit=top_k)
        chunks: list[RetrievedChunk] = []
        used = 0
        for hit in hits:
            knowledge_object = self._objects[hit.object_id]
            text = knowledge_object.normalized_statement or knowledge_object.verbatim_text
            if chunks and used + len(text) > max_total_chars:
                break  # respect the context budget once at least one chunk is included
            chunks.append(
                RetrievedChunk(
                    object_id=knowledge_object.id,
                    object_type=knowledge_object.object_type,
                    text=text,
                    score=hit.score,
                    source_version_id=knowledge_object.source_version_id,
                    anchor=_anchor(knowledge_object),
                )
            )
            used += len(text)
        return RetrievalContext(query=query, chunks=tuple(chunks))


def _anchor(knowledge_object: KnowledgeObject) -> str | None:
    anchor = knowledge_object.provenance.anchor
    return str(anchor) if anchor is not None else None
