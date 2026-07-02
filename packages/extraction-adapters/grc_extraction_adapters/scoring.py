"""A heuristic confidence scorer (implements ``ConfidenceScorerPort``).

Combines the available signals — the extractor's own confidence, the document classification
confidence, and any structural certainty — into a single final confidence by averaging. Pure and
deterministic; an ML calibrator would implement the same port later.
"""
from __future__ import annotations

from grc_domain.extraction import ExtractionCandidate
from grc_domain.shared.value_objects import Confidence
from grc_extraction import ConfidenceScorerPort, ScoringSignals

_NO_SIGNAL_CONFIDENCE = 0.5


class HeuristicConfidenceScorer(ConfidenceScorerPort):
    """Averages the present scoring signals into a final confidence."""

    async def score(self, candidate: ExtractionCandidate, *, signals: ScoringSignals) -> Confidence:
        scores: list[float] = []
        if signals.extractor_confidence is not None:
            scores.append(signals.extractor_confidence.score)
        if signals.classification_confidence is not None:
            scores.append(signals.classification_confidence.score)
        if signals.structural_certainty is not None:
            scores.append(signals.structural_certainty)
        if not scores:
            return Confidence(_NO_SIGNAL_CONFIDENCE)
        return Confidence(round(sum(scores) / len(scores), 4))
