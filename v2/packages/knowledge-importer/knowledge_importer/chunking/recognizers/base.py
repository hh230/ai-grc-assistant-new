"""Shared contract and helpers every Recognizer builds on. A Recognizer's whole job is
`detect_boundaries`: scan the document's lines and report where a structural unit
starts. Everything downstream of that (tree assembly, page tracking, oversized-unit
windowing, metadata stamping) is generic and lives in `chunking/text_lines.py` — a
Recognizer never builds a chunk itself."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

MAX_HEADING_LINE_LEN = 100
_TOC_DOT_LEADER = re.compile(r"\.{4,}")


@dataclass(frozen=True)
class Boundary:
    """One recognized structural start-point. `line_index` refers to the flat,
    page-aware line list `text_lines.split_into_lines` produces."""

    line_index: int
    level: int
    code: str | None
    title: str | None
    content_type: str = "section"


class RecognizerFn(Protocol):
    def __call__(self, lines: list[tuple[int, str]]) -> list[Boundary]: ...


def looks_like_toc_leader(line: str) -> bool:
    """A line with a run of 4+ dots is almost always a Table-of-Contents dot leader
    (`"4  Context of the organization  .......... 1"`), never a genuine heading — this
    is the one deliberately blunt filter this engine uses to avoid mistaking a ToC for
    real document structure, alongside simply bounding heading-line length (ToC lines
    with a trailing page number are typically far longer than a real heading line)."""
    return bool(_TOC_DOT_LEADER.search(line))


def numeric_level(code: str) -> int:
    """Nesting depth from a dotted/hyphenated numeric code, relative within one
    document: '4' -> 1, '4.2' -> 2, '4.2.1' -> 3, 'AC-2' -> 2, 'AC-2(1)' -> 3,
    '1-1-1' -> 3. Counts separators, not digit values or a fixed grammar per family —
    this is what lets one recognizer nest 'AC-2(1)' under 'AC-2', or a control under an
    NCA ECC domain, without hardcoding each standard's specific numbering scheme."""
    core = code.split("(")[0]
    level = core.count(".") + core.count("-") + 1
    if "(" in code:
        level += 1
    return level


def score_confidence(boundary_count: int, page_count: int | None, line_count: int) -> float:
    """A single, honest density heuristic: how many structural boundaries were found
    relative to how much document there is. The architecture doc (§3.7) describes a
    richer three-factor model (density + skeleton consistency + coverage); this ships
    the simplest version that correctly accepts/rejects real documents, since real ISO
    27001 text showed that "codes must be monotonically ascending" is not a safe hard
    rule (Annex A legitimately restarts numbering) — richer scoring, if it turns out to
    be needed, is exactly the "no threshold tuning yet" non-goal (§11) this document
    already named, not a gap introduced now."""
    if page_count and page_count > 0:
        expected = max(2, -(-page_count // 3))  # at least ~1 boundary every 3 pages
    else:
        expected = max(2, line_count // 200)
    return min(1.0, boundary_count / expected) if expected else 0.0
