"""The engine's one port — the stable abstraction seam (hexagonal architecture, CLAUDE.md §5).

The concrete, polite, robots.txt-respecting HTTP adapter lives in
``grc_knowledge_research_adapters``, built from ``grc_regulatory_crawlers``'s already-built
primitives rather than a second crawler (ADR-0025's explicit future-work note). This pure
package depends only on this abstraction — never on an HTTP library, a database, or the
network — the same separation ``grc_regulatory_intelligence.ports.CrawlerPort`` established.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from grc_knowledge_intelligence import SourceExcerpt, TrustedSource

from .models import DiscoveredDocumentRef


class ResearchCrawlerPort(ABC):
    """Discovers candidate documents at one trusted source, then fetches and normalizes one
    into a ``SourceExcerpt`` — the same excerpt shape ``KnowledgeDiscoveryEngine.discover``
    already accepts unmodified."""

    @abstractmethod
    async def discover(self, source: TrustedSource) -> tuple[DiscoveredDocumentRef, ...]: ...

    @abstractmethod
    async def fetch(self, source: TrustedSource, ref: DiscoveredDocumentRef) -> SourceExcerpt: ...
