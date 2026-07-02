"""A rule-based keyword classifier (implements ``ClassifierPort``).

Confirms a document's type by counting controlled keyword cues, returning the best match with a
confidence that grows with corroboration. Deterministic; no model. The confidence is surfaced to
the scorer as a signal — never hidden (CLAUDE.md §12).
"""
from __future__ import annotations

from collections.abc import Mapping

from grc_domain.knowledge import DocumentType
from grc_domain.shared.value_objects import Confidence
from grc_extraction import (
    ClassificationResult,
    ClassifierPort,
    NormalizedDocument,
    SegmentTree,
)

_DEFAULT_KEYWORDS: dict[str, DocumentType] = {
    "law": DocumentType.LAW,
    "regulation": DocumentType.EXECUTIVE_REGULATION,
    "standard": DocumentType.STANDARD,
    "iso": DocumentType.STANDARD,
    "control": DocumentType.STANDARD,
    "framework": DocumentType.FRAMEWORK,
    "policy": DocumentType.POLICY,
    "procedure": DocumentType.PROCEDURE,
}


class KeywordClassifier(ClassifierPort):
    """Picks the document type whose keyword cues appear most often."""

    def __init__(
        self,
        keyword_types: Mapping[str, DocumentType] | None = None,
        *,
        default_type: DocumentType = DocumentType.OTHER,
        base_confidence: float = 0.55,
    ) -> None:
        self._keyword_types = dict(keyword_types or _DEFAULT_KEYWORDS)
        self._default_type = default_type
        self._base_confidence = base_confidence

    async def classify(
        self, document: NormalizedDocument, *, segments: SegmentTree | None = None
    ) -> ClassificationResult:
        text = document.full_text.lower()
        scores: dict[DocumentType, int] = {}
        for keyword, document_type in self._keyword_types.items():
            occurrences = text.count(keyword)
            if occurrences:
                scores[document_type] = scores.get(document_type, 0) + occurrences

        if not scores:
            return ClassificationResult(
                document_type=self._default_type, confidence=Confidence(0.3)
            )

        best_type = max(scores, key=lambda dt: scores[dt])
        confidence = min(0.95, self._base_confidence + 0.1 * scores[best_type])
        return ClassificationResult(document_type=best_type, confidence=Confidence(confidence))
