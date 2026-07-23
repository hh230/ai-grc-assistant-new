"""`TenantKnowledgeBase` — a mutable, in-memory knowledge base of a tenant's ingested documents.

It **consumes** `retrieval-engine`'s `InMemoryCorpus` and providers rather than re-implementing it:
chunks are appended at runtime and searched through the same `KeywordSearchProvider` the frozen
`RetrievalEngine` already uses. Every chunk it holds is tenant-scoped (`scope_kind=ORGANIZATION`,
`organization_id=<tenant>`), so the engine's tenant filtering / defence-in-depth keeps one tenant's
uploaded data invisible to another.

The in-memory store is deliberately swappable: in production the same chunks are written to pgvector
(`PgVectorProvider`, same provider interface), and nothing above this changes.
"""

from __future__ import annotations

from collections.abc import Iterable

from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.interfaces import CorpusChunk


class TenantKnowledgeBase:
    """A growable corpus of ingested chunks, searchable via a keyword provider. Chunks carry their
    own tenant scope, so a single base can hold many tenants' data and retrieval never crosses the
    boundary (a query is always scoped to one tenant)."""

    def __init__(self) -> None:
        self._corpus = InMemoryCorpus.from_chunks([])

    def add(self, chunks: Iterable[CorpusChunk]) -> int:
        """Append chunks to the base; returns how many were added."""
        added = 0
        for chunk in chunks:
            self._corpus.chunks.append(chunk)
            self._corpus.by_id[chunk.chunk_id] = chunk
            added += 1
        return added

    @property
    def corpus(self) -> InMemoryCorpus:
        return self._corpus

    def keyword_provider(self) -> InMemoryKeywordProvider:
        """A `KeywordSearchProvider` over the ingested chunks — plug into a `RetrievalEngine` or a
        `search-tools` local/hybrid search."""
        return InMemoryKeywordProvider(self._corpus)

    def __len__(self) -> int:
        return len(self._corpus.chunks)
