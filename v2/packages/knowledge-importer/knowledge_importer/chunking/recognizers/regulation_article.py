"""RegulationArticleRecognizer — Article/Chapter structure for the `law` and
`regulation` Document Profiles (Saudi Laws, Saudi Regulations, CMA, SDAIA, NCA ECC).

Calibrated against real extracted text (Saudi Companies Law and others): Arabic legal
drafting spells article numbers as ordinal words ("المادة الأولى", "المادة الثانية"),
not digits, and groups articles under "الباب" (Part) and "الفصل" (Chapter). Both are
matched verbatim — no attempt is made to translate an Arabic ordinal word into an
integer; `code` stores exactly what the source says, per the "never rewrite content"
rule. English "Article N" / "Chapter N" and NCA ECC's domain-control-subcontrol grammar
(`1-1-1`, `2-2-P-1`) are matched for bilingual or hybrid sources.
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

_ARABIC_ARTICLE = re.compile(r"^المادة\s+([^\n:]{1,40}?)[:.]\s*(.*)$")
_ARABIC_ARTICLE_NO_SEP = re.compile(r"^المادة\s+(\([^)]{1,30}\)|[^\n]{1,30})$")
_ARABIC_PART = re.compile(r"^الباب\s+(.{1,40})$")
_ARABIC_CHAPTER = re.compile(r"^الفصل\s+(.{1,40})$")

_ENGLISH_ARTICLE = re.compile(rf"^Article\s+(\d+[A-Za-z]?)[:.]?\s*(.{{0,{_TITLE_LEN}}})$", re.IGNORECASE)
_ENGLISH_CHAPTER = re.compile(rf"^(Chapter|Part)\s+(\w+)[:.]?\s*(.{{0,{_TITLE_LEN}}})$", re.IGNORECASE)
_NCA_ECC_CODE = re.compile(rf"^(\d+-\d+(?:-[A-Za-z]+)?-\d+)\s+([A-Za-z؀-ۿ].{{1,{_TITLE_LEN}}})$")


def detect_boundaries(lines: list[tuple[int, str]]) -> list[Boundary]:
    boundaries: list[Boundary] = []
    for idx, (_page, raw_line) in enumerate(lines):
        line = raw_line.strip()
        if not line or len(line) > MAX_HEADING_LINE_LEN or looks_like_toc_leader(line):
            continue

        match = _ARABIC_PART.match(line)
        if match:
            boundaries.append(Boundary(line_index=idx, level=1, code=match.group(1).strip(), title=None))
            continue

        match = _ARABIC_CHAPTER.match(line)
        if match:
            boundaries.append(Boundary(line_index=idx, level=2, code=match.group(1).strip(), title=None))
            continue

        match = _ARABIC_ARTICLE.match(line)
        if match:
            code, title = match.group(1).strip(), match.group(2).strip()
            boundaries.append(Boundary(line_index=idx, level=3, code=code, title=title or None))
            continue

        match = _ARABIC_ARTICLE_NO_SEP.match(line)
        if match:
            boundaries.append(Boundary(line_index=idx, level=3, code=match.group(1).strip(), title=None))
            continue

        match = _ENGLISH_CHAPTER.match(line)
        if match:
            code = f"{match.group(1)} {match.group(2)}"
            boundaries.append(Boundary(line_index=idx, level=1, code=code, title=match.group(3).strip() or None))
            continue

        match = _ENGLISH_ARTICLE.match(line)
        if match:
            title = match.group(2).strip()
            boundaries.append(
                Boundary(line_index=idx, level=3, code=f"Article {match.group(1)}", title=title or None)
            )
            continue

        match = _NCA_ECC_CODE.match(line)
        if match:
            code, title = match.group(1), match.group(2).strip()
            boundaries.append(Boundary(line_index=idx, level=numeric_level(code), code=code, title=title))
            continue

    return boundaries
