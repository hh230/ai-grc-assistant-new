"""PolicyProcedureRecognizer — two modes sharing one implementation, selected by the
assigned Document Profile's `skeleton.mode` (`"policy"` for `corporate_policy`,
`"procedure"` for `procedure`), per the "one Recognizer, several Profiles" design (§2).

Policy mode leans on vocabulary matching more than any other recognizer, because real
policy documents have the least standardized structure of any genre here — calibrated
against a real corporate Code of Conduct PDF, whose actual section titles ("MESSAGE FROM
THE CEO", "SGS VISION & VALUES", "COMPLIANCE WITH LEGAL REQUIREMENTS") are short
ALL-CAPS lines, not the neat "1. Purpose" numbering the architecture doc's illustrative
vocabulary list might suggest is universal. Numbered headings and the controlled
vocabulary are both still recognized where present; ALL-CAPS detection is what makes
this recognizer work on documents that have neither.

Procedure mode is pattern-based (ordered/lettered steps) and has not been calibrated
against a real procedure document in this corpus — flagged honestly, not claimed
validated to the same degree as the other recognizers.
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

_NUMBERED_HEADING = re.compile(rf"^(\d+(?:\.\d+)*)\.?\s+([A-Za-z].{{1,{_TITLE_LEN}}})$")

_POLICY_VOCABULARY = frozenset(
    {
        "purpose",
        "scope",
        "roles and responsibilities",
        "responsibilities",
        "policy statement",
        "enforcement",
        "definitions",
        "review cycle",
        "applicability",
        "overview",
        "background",
        "compliance",
        "exceptions",
        "related documents",
        "references",
        "introduction",
    }
)

_STEP_LABEL = re.compile(rf"^(Step\s*\d+|\d+\))[:.]?\s*(.{{0,{_TITLE_LEN}}})$", re.IGNORECASE)
_LETTERED_SUBSTEP = re.compile(rf"^\(?([a-z])\)\s+(.{{1,{_TITLE_LEN}}})$")


def _is_all_caps_heading(line: str) -> bool:
    if not (3 <= len(line) <= 80):
        return False
    if line[-1] in ".,;":
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 3:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return (upper / len(letters)) >= 0.8


def _matches_vocabulary(line: str) -> bool:
    normalized = re.sub(r"^\d+(\.\d+)*\.?\s*", "", line.strip().lower())
    return normalized in _POLICY_VOCABULARY


def _detect_policy_boundaries(lines: list[tuple[int, str]]) -> list[Boundary]:
    boundaries: list[Boundary] = []
    for idx, (_page, raw_line) in enumerate(lines):
        line = raw_line.strip()
        if not line or len(line) > MAX_HEADING_LINE_LEN or looks_like_toc_leader(line):
            continue

        match = _NUMBERED_HEADING.match(line)
        if match and (_matches_vocabulary(line) or numeric_level(match.group(1)) == 1):
            code, title = match.group(1), match.group(2).strip()
            boundaries.append(Boundary(line_index=idx, level=numeric_level(code), code=code, title=title))
            continue

        if _matches_vocabulary(line) or _is_all_caps_heading(line):
            boundaries.append(Boundary(line_index=idx, level=1, code=None, title=line))
            continue

    return boundaries


def _detect_procedure_boundaries(lines: list[tuple[int, str]]) -> list[Boundary]:
    boundaries: list[Boundary] = []
    for idx, (_page, raw_line) in enumerate(lines):
        line = raw_line.strip()
        if not line or len(line) > MAX_HEADING_LINE_LEN or looks_like_toc_leader(line):
            continue

        match = _STEP_LABEL.match(line)
        if match:
            boundaries.append(Boundary(line_index=idx, level=1, code=match.group(1), title=match.group(2).strip() or None))
            continue

        match = _LETTERED_SUBSTEP.match(line)
        if match:
            boundaries.append(Boundary(line_index=idx, level=2, code=f"({match.group(1)})", title=match.group(2).strip()))
            continue

    return boundaries


def detect_boundaries(lines: list[tuple[int, str]], mode: str = "policy") -> list[Boundary]:
    if mode == "procedure":
        return _detect_procedure_boundaries(lines)
    return _detect_policy_boundaries(lines)
