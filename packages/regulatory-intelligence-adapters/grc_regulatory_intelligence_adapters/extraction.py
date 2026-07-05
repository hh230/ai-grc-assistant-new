"""A deterministic, rule-based ``ObligationExtractorPort`` — no AI, no external dependency
beyond the stdlib ``re`` module. Splits regulatory text on numbered clauses when the source
uses them (the common case for laws/regulations/standards), falling back to sentence
boundaries otherwise, while preserving accurate character offsets into the source document.
"""

from __future__ import annotations

import re

from grc_regulatory_intelligence import ObligationCandidate, RawRegulatoryDocument
from grc_regulatory_intelligence.ports import ObligationExtractorPort

_NUMBERED_CLAUSE = re.compile(r"(?:(?<=\n)|^)\s*\d+[.)]\s+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")

# Below this length a span is treated as noise (a lone marker, a heading fragment, ...)
# rather than an atomic obligation.
_MIN_OBLIGATION_LENGTH = 15


class RuleBasedObligationExtractor(ObligationExtractorPort):
    """The reference ``ObligationExtractorPort`` adapter: deterministic clause/sentence
    splitting with offset-accurate candidates."""

    async def extract(self, document: RawRegulatoryDocument) -> tuple[ObligationCandidate, ...]:
        raw_text = document.raw_text
        candidates: list[ObligationCandidate] = []
        for start, end in _spans(raw_text):
            trimmed = _trim_span(raw_text, start, end)
            if trimmed is None:
                continue
            trimmed_start, trimmed_end = trimmed
            text = raw_text[trimmed_start:trimmed_end]
            if len(text) < _MIN_OBLIGATION_LENGTH:
                continue
            candidates.append(
                ObligationCandidate(
                    obligation_text=text,
                    source_char_start=trimmed_start,
                    source_char_end=trimmed_end,
                )
            )
        return tuple(candidates)


def _spans(raw_text: str) -> list[tuple[int, int]]:
    """Half-open ``(start, end)`` spans over ``raw_text``, before trimming."""
    markers = [match.start() for match in _NUMBERED_CLAUSE.finditer(raw_text)]
    if len(markers) >= 2:
        boundaries = [*markers, len(raw_text)]
        # Lengths intentionally differ by one (boundaries[1:] drops the first marker) — zip
        # correctly truncates to len(markers) pairs.
        return list(zip(boundaries, boundaries[1:], strict=False))

    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in _SENTENCE_BOUNDARY.finditer(raw_text):
        spans.append((cursor, match.start()))
        cursor = match.end()
    spans.append((cursor, len(raw_text)))
    return spans


def _trim_span(raw_text: str, start: int, end: int) -> tuple[int, int] | None:
    """Shrink a span to exclude leading/trailing whitespace, so offsets point exactly at the
    obligation text stored downstream. Returns ``None`` if nothing but whitespace remains."""
    segment = raw_text[start:end]
    left_padding = len(segment) - len(segment.lstrip())
    right_padding = len(segment) - len(segment.rstrip())
    trimmed_start = start + left_padding
    trimmed_end = end - right_padding
    if trimmed_end <= trimmed_start:
        return None
    return trimmed_start, trimmed_end
