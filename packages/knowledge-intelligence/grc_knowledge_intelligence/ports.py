"""The engine's ports — the stable abstraction seams (hexagonal architecture, CLAUDE.md §5).

The concrete, Tool-audited, LLM-backed adapter lives in
``grc_knowledge_intelligence_adapters``; this pure package depends only on this abstraction —
never on an LLM SDK, a database, or the network — the same separation
``grc_regulatory_intelligence.ports`` established for obligation classification.

Deliberately **no fetch/research port** in this phase: KI-P1 does not crawl trusted sources
itself. A ``SourceExcerpt`` (already-fetched text) is an input the caller provides — see
ADR-0025's future-work note on reusing ``grc_regulatory_crawlers`` for real fetching in a
later phase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import KnowledgeAnswer, KnowledgeQuestion, SourceExcerpt


class KnowledgeExtractorPort(ABC):
    """Synthesizes a candidate answer to one question from one already-fetched source
    excerpt.

    Implementations must return a fully valid ``KnowledgeAnswer`` or raise
    ``KnowledgeExtractionError`` — never a partially-populated or unvalidated result, the same
    contract ``ObligationClassifierPort`` holds its implementations to.
    """

    @abstractmethod
    async def extract(
        self, question: KnowledgeQuestion, excerpt: SourceExcerpt
    ) -> KnowledgeAnswer: ...
