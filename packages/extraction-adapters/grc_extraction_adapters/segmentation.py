"""A rule-based heading segmenter (implements ``SegmenterPort``).

Recovers a document's logical skeleton with a simple, deterministic grammar: lines that look like
``Article 5``, ``Section 3.1``, ``Annex A`` (or a leading ``5.2 ...`` numbering) open a new
segment with a stable ``StructuralAnchor``; following lines accrue to it. Content before the first
heading becomes a ``preamble`` segment so nothing is dropped. The structural role is inferred from
deontic cues so the engine can route the right extractors. Citations point at the anchor — not at
a chunk id — so they survive re-processing (CLAUDE.md §12; Knowledge-First provenance).
"""
from __future__ import annotations

import re

from grc_domain.knowledge import SectionType, StructuralAnchor, TextSpan
from grc_extraction import (
    ExtractionProfile,
    NormalizedDocument,
    Segment,
    SegmenterPort,
    SegmentRole,
    SegmentTree,
)

_KEYWORD_SECTION_TYPES: dict[str, SectionType] = {
    "part": SectionType.PART,
    "chapter": SectionType.CHAPTER,
    "article": SectionType.ARTICLE,
    "clause": SectionType.CLAUSE,
    "section": SectionType.SECTION,
    "annex": SectionType.ANNEX,
    "schedule": SectionType.SCHEDULE,
    "appendix": SectionType.APPENDIX,
}

_KEYWORD_HEADING = re.compile(
    r"^(?P<keyword>part|chapter|article|clause|section|annex|schedule|appendix)\s+"
    r"(?P<code>[A-Za-z0-9][\w.\-]*)\b[:.)]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
_NUMBERED_HEADING = re.compile(r"^(?P<code>\d+(?:\.\d+)*)[.)]?\s+(?P<rest>.+)$")

_DEFINITION_CUE = re.compile(r"\bmeans\b", re.IGNORECASE)
_MANDATORY_CUE = re.compile(r"\b(shall|must)\b", re.IGNORECASE)
_RECOMMENDED_CUE = re.compile(r"\bshould\b", re.IGNORECASE)


class HeadingSegmenter(SegmenterPort):
    """Splits a normalized document into anchored, role-tagged segments."""

    def __init__(self, *, name: str = "heading", version: str = "1.0.0") -> None:
        self._name = name
        self._version = version

    async def segment(
        self, document: NormalizedDocument, *, profile: ExtractionProfile
    ) -> SegmentTree:
        groups: list[tuple[StructuralAnchor, list[str]]] = []
        for block in document.blocks:
            anchor = _heading_anchor(block.text)
            if anchor is not None:
                rest = _heading_remainder(block.text)
                groups.append((anchor, [rest] if rest else []))
            else:
                if not groups:
                    groups.append((StructuralAnchor(SectionType.SECTION, "preamble"), []))
                groups[-1][1].append(block.text)

        segments = tuple(
            _build_segment(anchor, lines, position)
            for position, (anchor, lines) in enumerate(groups)
        )
        return SegmentTree(segments)


def _heading_anchor(text: str) -> StructuralAnchor | None:
    keyword_match = _KEYWORD_HEADING.match(text)
    if keyword_match is not None:
        section_type = _KEYWORD_SECTION_TYPES[keyword_match.group("keyword").lower()]
        return StructuralAnchor(section_type, keyword_match.group("code"))
    numbered_match = _NUMBERED_HEADING.match(text)
    if numbered_match is not None:
        return StructuralAnchor(SectionType.SECTION, numbered_match.group("code"))
    return None


def _heading_remainder(text: str) -> str:
    keyword_match = _KEYWORD_HEADING.match(text)
    if keyword_match is not None:
        return keyword_match.group("rest").strip()
    numbered_match = _NUMBERED_HEADING.match(text)
    if numbered_match is not None:
        return numbered_match.group("rest").strip()
    return ""


def _build_segment(anchor: StructuralAnchor, lines: list[str], position: int) -> Segment:
    text = " ".join(line for line in lines if line).strip() or str(anchor)
    return Segment(
        anchor=anchor,
        text=text,
        role=_infer_role(text),
        text_span=TextSpan(0, len(text)),
        position=position,
    )


def _infer_role(text: str) -> SegmentRole:
    if _DEFINITION_CUE.search(text):
        return SegmentRole.DEFINITION
    if _MANDATORY_CUE.search(text) or _RECOMMENDED_CUE.search(text):
        return SegmentRole.NORMATIVE
    return SegmentRole.OTHER
