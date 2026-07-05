"""The engine's ports — the stable abstraction seams (hexagonal architecture, CLAUDE.md §5).

Concrete adapters (a rule-based clause splitter, an LLM-backed classifier, ...) implement
these in ``grc_regulatory_intelligence_adapters``. The engine depends only on these
abstractions — never on a connector, an LLM SDK, or a database — which is what lets AI-assisted
classification plug in without coupling the pure pipeline to it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .artifacts import ObligationCandidate, ObligationClassification, RawRegulatoryDocument
from .documents import DiscoveredDocumentRef, RegulatoryDocumentInput
from .sources import RegulatorySource


class CrawlerPort(ABC):
    """Discovers candidate documents at one regulatory source, then fetches and normalizes
    one. Concrete adapters (HTTP, RSS, ...) live in ``grc_regulatory_crawlers``; this port is
    what lets ``RegulatoryCrawlerRunner`` orchestrate any of them identically."""

    @abstractmethod
    async def discover(self, source: RegulatorySource) -> tuple[DiscoveredDocumentRef, ...]: ...

    @abstractmethod
    async def fetch(
        self, source: RegulatorySource, ref: DiscoveredDocumentRef
    ) -> RegulatoryDocumentInput: ...


class ObligationExtractorPort(ABC):
    """Splits a regulatory document into atomic obligation candidates."""

    @abstractmethod
    async def extract(self, document: RawRegulatoryDocument) -> tuple[ObligationCandidate, ...]: ...


class ObligationClassifierPort(ABC):
    """Classifies one obligation candidate.

    Implementations must return a fully valid ``ObligationClassification`` or raise
    ``grc_regulatory_intelligence.exceptions.ObligationClassificationError`` — never return a
    partially-populated or unvalidated result. Rejecting malformed output is the adapter's
    responsibility (e.g. pydantic validation over an LLM's structured response); the engine
    only knows how to handle the two outcomes (a valid classification, or that error).
    """

    @abstractmethod
    async def classify(
        self, candidate: ObligationCandidate, *, document: RawRegulatoryDocument
    ) -> ObligationClassification: ...
