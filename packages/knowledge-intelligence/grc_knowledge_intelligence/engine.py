"""The Knowledge Discovery pipeline coordinator (pure orchestration, CLAUDE.md §12-13).

``KnowledgeDiscoveryEngine`` turns one question + one already-fetched trusted-source excerpt
into a candidate ``KnowledgeItem`` via the injected ``KnowledgeExtractorPort`` — mirroring
``RegulatoryIntelligenceEngine``'s shape exactly: it depends only on the port and the models
in this package, never on an LLM SDK, a database, or the network. Fetching the excerpt itself
(discovering and crawling a trusted source) is a later phase's concern — see ADR-0025.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable

from .enums import VerificationStatus
from .exceptions import KnowledgeExtractionError
from .models import KnowledgeItem, KnowledgeQuestion, SourceExcerpt
from .ports import KnowledgeExtractorPort


def compute_version_hash(question: KnowledgeQuestion, excerpt: SourceExcerpt) -> str:
    """A deterministic fingerprint of one discovery, stable across pipeline re-runs — derived
    only from the question and the excerpt's own content, never a timestamp or run id, so a
    storage layer can upsert on this key instead of duplicating rows (the same contract
    ``grc_regulatory_intelligence.compute_version_hash`` already established)."""
    payload = "|".join((question.question_id, excerpt.source.source_id, excerpt.text))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class KnowledgeDiscoveryEngine:
    """Synthesizes one candidate ``KnowledgeItem`` per (question, excerpt) pair. Every
    discovery starts ``VerificationStatus.DISCOVERED`` with ``last_verified=None`` and
    ``version=1`` — knowledge is never treated as absolute the moment it is found (ADR-0025
    §6); only an explicit human decision, applied later by the storage layer, moves it
    forward.
    """

    def __init__(
        self,
        *,
        extractor: KnowledgeExtractorPort,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._extractor = extractor
        self._id_factory = id_factory

    async def discover(
        self, question: KnowledgeQuestion, excerpt: SourceExcerpt
    ) -> KnowledgeItem | None:
        """Returns ``None`` (rather than raising) when the extractor cannot ground an answer
        in this excerpt — a failed discovery is recorded by the caller as "still a gap", not
        guessed at (CLAUDE.md §16: fail safe, not open)."""
        try:
            answer = await self._extractor.extract(question, excerpt)
        except KnowledgeExtractionError:
            return None

        return KnowledgeItem(
            id=self._id_factory(),
            question_id=question.question_id,
            question=question.question,
            answer=answer.answer,
            domain=question.domain,
            category=question.category,
            applicable_context=answer.applicable_context,
            source=excerpt.source,
            citation=f"{excerpt.source.source_id}#{question.question_id}",
            jurisdiction=excerpt.source.jurisdiction,
            confidence=answer.confidence,
            status=VerificationStatus.DISCOVERED,
            last_verified=None,
            version=1,
        )
