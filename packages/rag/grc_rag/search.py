"""Lexical, metadata-filtered search over knowledge objects (Handbook §8 milestone 9).

A pure, deterministic keyword index: it tokenizes each ``KnowledgeObject``'s text, scores a query
by normalized term-frequency overlap, and returns ranked, tenant-scoped results filtered by type.
This is the keyword half of the hybrid retrieval the architecture calls for (CLAUDE.md §12); the
semantic (vector) half plugs in behind the retrieval layer once an embedding provider is selected.
Tenant isolation is absolute: an index holds a single ``KnowledgeScope``.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from grc_domain.knowledge import KnowledgeObject, KnowledgeObjectType, KnowledgeScope
from grc_domain.shared.identifiers import KnowledgeObjectId

from .exceptions import CrossScopeError

# Minimal generic stopwords. Deontic terms (shall/must/should) are deliberately kept — they are
# meaningful in compliance text.
_STOPWORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "is", "be", "by", "as", "it"}
)
_TOKEN_SPLIT = re.compile(r"[^0-9a-z]+")


@dataclass(frozen=True)
class SearchResult:
    """A ranked hit: the object, its type, and a relevance score in (0, 1]."""

    object_id: KnowledgeObjectId
    object_type: KnowledgeObjectType
    score: float


@dataclass(frozen=True)
class _IndexedDocument:
    object_id: KnowledgeObjectId
    object_type: KnowledgeObjectType
    term_counts: Counter[str]
    length: int


class LexicalSearchIndex:
    """An in-memory lexical index over knowledge objects for one tenant scope."""

    def __init__(self, scope: KnowledgeScope) -> None:
        self._scope = scope
        self._documents: dict[KnowledgeObjectId, _IndexedDocument] = {}

    @property
    def scope(self) -> KnowledgeScope:
        return self._scope

    @property
    def size(self) -> int:
        return len(self._documents)

    def index(self, knowledge_object: KnowledgeObject) -> None:
        if knowledge_object.scope != self._scope:
            raise CrossScopeError(f"object {knowledge_object.id} is outside the index's scope")
        tokens = _tokenize(_document_text(knowledge_object))
        self._documents[knowledge_object.id] = _IndexedDocument(
            object_id=knowledge_object.id,
            object_type=knowledge_object.object_type,
            term_counts=Counter(tokens),
            length=len(tokens),
        )

    def search(
        self,
        query: str,
        *,
        object_type: KnowledgeObjectType | None = None,
        limit: int = 10,
    ) -> tuple[SearchResult, ...]:
        if limit <= 0:
            raise ValueError("limit must be > 0")
        query_terms = set(_tokenize(query))
        if not query_terms:
            return ()
        results = [
            SearchResult(
                object_id=document.object_id,
                object_type=document.object_type,
                score=score,
            )
            for document in self._documents.values()
            if (object_type is None or document.object_type is object_type)
            and (score := _score(query_terms, document)) > 0.0
        ]
        # Descending score; stable, deterministic tie-break by object id.
        results.sort(key=lambda result: (-result.score, str(result.object_id)))
        return tuple(results[:limit])


def _document_text(knowledge_object: KnowledgeObject) -> str:
    parts = [knowledge_object.verbatim_text]
    if knowledge_object.normalized_statement:
        parts.append(knowledge_object.normalized_statement)
    return " ".join(parts)


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN_SPLIT.split(text.lower())
        if len(token) >= 2 and token not in _STOPWORDS
    ]


def _score(query_terms: set[str], document: _IndexedDocument) -> float:
    if document.length == 0:
        return 0.0
    matched = sum(
        document.term_counts[term] for term in query_terms if term in document.term_counts
    )
    return round(matched / document.length, 6)
