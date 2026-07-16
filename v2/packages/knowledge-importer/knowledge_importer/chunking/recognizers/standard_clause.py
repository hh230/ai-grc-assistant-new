"""StandardClauseRecognizer — hierarchical clause/control numbering. Serves both the
`iso_standard` and `control_framework` Document Profiles (ISO, NIST, COBIT, COSO): the
same numbering-recognition code, parameterized only by which Document Profile assigned
it, per the "Profile is data, Recognizer is code" split (architecture doc §2.2).

Patterns are calibrated against real extracted text (ISO/IEC 27001:2022): main-body
clauses (`4`, `4.2`, `4.2.1`) and Annex A controls, which the 2022 edition numbers as
plain decimals (`5.1`, `8.34`, not `A.5.1`) — both forms are matched. NIST CSF
(`PR.AC-1`) and NIST SP 800-53 (`AC-2`, `AC-2(1)`, the enhancement suffix nesting under
its base control) are matched by separate patterns for `control_framework` documents.
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

_DECIMAL_CLAUSE = re.compile(rf"^(?:A\.)?(\d+(?:\.\d+)*)\s+([A-Z].{{1,{_TITLE_LEN}}})$")
_NIST_CSF = re.compile(rf"^([A-Z]{{2}}\.[A-Z]{{2}}(?:-\d+)?)\s+([A-Za-z].{{1,{_TITLE_LEN}}})$")
_NIST_800_53 = re.compile(rf"^([A-Z]{{2}}-\d+(?:\(\d+\))?)\s+([A-Za-z].{{1,{_TITLE_LEN}}})$")

_PATTERNS = (_DECIMAL_CLAUSE, _NIST_CSF, _NIST_800_53)


def detect_boundaries(lines: list[tuple[int, str]]) -> list[Boundary]:
    boundaries: list[Boundary] = []
    for idx, (_page, raw_line) in enumerate(lines):
        line = raw_line.strip()
        if not line or len(line) > MAX_HEADING_LINE_LEN or looks_like_toc_leader(line):
            continue
        for pattern in _PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            code, title = match.group(1), match.group(2).strip()
            boundaries.append(Boundary(line_index=idx, level=numeric_level(code), code=code, title=title))
            break
    return boundaries
