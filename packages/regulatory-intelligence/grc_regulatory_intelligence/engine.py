"""The Regulatory Intelligence pipeline coordinator (pure orchestration, CLAUDE.md §12-13).

``RegulatoryIntelligenceEngine`` drives one ``RawRegulatoryDocument`` through two stages —
split into atomic obligation candidates, then classify each one — via the injected ports.
It depends only on the ports and the artifacts in this package: never on a connector, an LLM
SDK, or a database. Concrete adapters that implement the ports live in
``grc_regulatory_intelligence_adapters``.
"""

from __future__ import annotations

from .artifacts import (
    ClassifiedObligation,
    ObligationCandidate,
    ObligationClassification,
    RawRegulatoryDocument,
    RegulatoryIntelligenceResult,
    compute_version_hash,
)
from .exceptions import ObligationClassificationError
from .ports import ObligationClassifierPort, ObligationExtractorPort


class RegulatoryIntelligenceEngine:
    """Turns one raw regulatory document into structured, classified obligations.

    Classification failures are isolated per-candidate (CLAUDE.md §16: fail safe, not open):
    an obligation whose classifier call could not produce valid output is still recorded —
    with ``ObligationClassification.unclassified()`` and ``pending_review`` — rather than
    silently dropped or guessed at, and the run continues for the remaining candidates.
    """

    def __init__(
        self, *, extractor: ObligationExtractorPort, classifier: ObligationClassifierPort
    ) -> None:
        self._extractor = extractor
        self._classifier = classifier

    async def run(self, document: RawRegulatoryDocument) -> RegulatoryIntelligenceResult:
        candidates = await self._extractor.extract(document)

        obligations: list[ClassifiedObligation] = []
        failed_classifications = 0
        for candidate in candidates:
            classification = await self._classify_safely(candidate=candidate, document=document)
            if classification is None:
                failed_classifications += 1
                classification = ObligationClassification.unclassified()

            obligations.append(
                ClassifiedObligation(
                    candidate=candidate,
                    classification=classification,
                    version_hash=compute_version_hash(document, candidate),
                    # Regulatory Intelligence never auto-confirms an AI classification
                    # (CLAUDE.md §1) — every obligation starts pending a human review.
                )
            )

        return RegulatoryIntelligenceResult(
            document=document,
            obligations=tuple(obligations),
            failed_classifications=failed_classifications,
        )

    async def _classify_safely(
        self, *, candidate: ObligationCandidate, document: RawRegulatoryDocument
    ) -> ObligationClassification | None:
        try:
            return await self._classifier.classify(candidate, document=document)
        except ObligationClassificationError:
            return None
