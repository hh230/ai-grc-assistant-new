"""ContractClauseRecognizer — numbered clause hierarchy, defined terms, and
schedules/annexes/exhibits for the `contract` Document Profile.

Numbered clauses (`1.`, `1.1`) reuse the same generic numeric-level logic as
`standard_clause`. Lettered/roman sub-clauses (`(a)`, `(i)`) nest one level deeper than
whatever numbered clause precedes them. Schedules/Annexes/Exhibits are recognized as
top-level structural siblings to the clause body, never as children of whatever clause
happens to precede them in the text. Defined-term tagging (`content_type: "definition"`)
is applied as a metadata-only post-pass in `engine.py`, not here — this module only
detects boundaries.
"""

from __future__ import annotations

import re

from knowledge_importer.chunking.recognizers.base import (
    MAX_HEADING_LINE_LEN,
    Boundary,
    looks_like_toc_leader,
    numeric_level,
)

_TITLE_LEN = MAX_HEADING_LINE_LEN - 20

_NUMBERED_CLAUSE = re.compile(rf"^(\d+(?:\.\d+)*)\.?\s+([A-Z].{{1,{_TITLE_LEN}}})$")
_LETTERED_SUBCLAUSE = re.compile(rf"^\(([a-z]|[ivxlcdm]+)\)\s+([A-Za-z].{{1,{_TITLE_LEN}}})$")
_SCHEDULE = re.compile(rf"^(Schedule|Annex|Exhibit)\s+(\w+)[:.]?\s*(.{{0,{_TITLE_LEN}}})$", re.IGNORECASE)

DEFINED_TERM_PATTERN = re.compile(r"\"([A-Z][\w\s]{2,60})\"\s+means\b")


def detect_boundaries(lines: list[tuple[int, str]]) -> list[Boundary]:
    boundaries: list[Boundary] = []
    last_clause_level = 0
    for idx, (_page, raw_line) in enumerate(lines):
        line = raw_line.strip()
        if not line or len(line) > MAX_HEADING_LINE_LEN or looks_like_toc_leader(line):
            continue

        match = _SCHEDULE.match(line)
        if match:
            code = f"{match.group(1)} {match.group(2)}"
            boundaries.append(Boundary(line_index=idx, level=1, code=code, title=match.group(3).strip() or None))
            last_clause_level = 0
            continue

        match = _NUMBERED_CLAUSE.match(line)
        if match:
            code, title = match.group(1), match.group(2).strip()
            level = numeric_level(code)
            boundaries.append(Boundary(line_index=idx, level=level, code=code, title=title))
            last_clause_level = level
            continue

        match = _LETTERED_SUBCLAUSE.match(line)
        if match:
            code, title = match.group(1), match.group(2).strip()
            level = max(last_clause_level, 1) + 1
            boundaries.append(Boundary(line_index=idx, level=level, code=f"({code})", title=title))
            continue

    return boundaries
