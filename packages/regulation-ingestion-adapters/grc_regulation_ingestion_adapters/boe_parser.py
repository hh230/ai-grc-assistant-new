"""Deterministic, Arabic-aware parser for a Saudi Board of Experts (``laws.boe.gov.sa``) law
page (Knowledge Intelligence KI-P6, ADR-0030) — no LLM, matching this repo's existing posture
of preferring a reviewable, reproducible pattern wherever one suffices (the same choice
KI-P1's gap detector and KI-P2's research planner already made).

Confirmed live against a real page (`النظام الأساسي للحكم` / Basic Law of Governance): a BOE
page's metadata block names the law (Arabic + English), its issuance/publication dates,
in-force status, and issuing instrument; its body is organized into chapters (``الباب``) and
articles (``المادة``), with an article's own amendment history — if any — appearing directly
beneath it under a ``تعديلات المادة`` heading, describing which Royal Order changed it and how.

One legal unit is never split across two ``KnowledgeSection``-shaped results: the ``المادة``
heading is the one hard boundary an amendment block can attach to but never crosses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_METADATA_PATTERNS: dict[str, re.Pattern[str]] = {
    "name_en": re.compile(r"Law name\n(.+)"),
    "issuance_date": re.compile(r"تاريخ الإصدار\n(.+)"),
    "publication_date": re.compile(r"تاريخ النشر\n(.+)"),
    "status": re.compile(r"الحالة\n(.+)"),
    "official_citation": re.compile(r"أدوات إصدار النظام\n(.+)"),
}

# A chapter heading line, e.g. "الباب الأول :  المبادئ العامة" — code + an optional title.
_CHAPTER_RE = re.compile(r"^الباب\s+([^\n:：]+?)\s*[:：]\s*(.*)$", re.MULTILINE)
# An article heading line, e.g. "المادة الخامسة" — just the code, title is the body that
# follows until the next heading.
_ARTICLE_RE = re.compile(r"^المادة\s+(\S+)\s*$", re.MULTILINE)
_AMENDMENT_HEADING = "تعديلات المادة"


@dataclass(frozen=True)
class ParsedSection:
    """One legal unit ready to become a `NewRegulationSection` — chapter or article, never a
    fragment of one."""

    section_type: str  # "chapter" | "article"
    code: str
    path: tuple[str, ...]
    position: int
    title_ar: str | None = None
    text_ar: str | None = None
    amendment_note_ar: str | None = None
    parent_index: int | None = None  # index into ParsedRegulation.sections, resolved by caller


@dataclass(frozen=True)
class ParsedRegulation:
    name_ar: str
    name_en: str | None
    issuance_date_raw: str | None
    publication_date_raw: str | None
    status_ar: str | None
    official_citation: str | None
    sections: tuple[ParsedSection, ...] = field(default_factory=tuple)


def _extract_metadata(text: str) -> dict[str, str | None]:
    metadata: dict[str, str | None] = {}
    for key, pattern in _METADATA_PATTERNS.items():
        match = pattern.search(text)
        metadata[key] = match.group(1).strip() if match else None
    return metadata


def _split_amendment(article_body: str) -> tuple[str, str | None]:
    """An article's own body may end with its amendment history. Returns
    ``(clean_text, amendment_note)`` — the amendment note is never part of the article's own
    legal text."""
    marker = article_body.find(_AMENDMENT_HEADING)
    if marker == -1:
        return article_body.strip(), None
    return article_body[:marker].strip(), article_body[marker:].strip()


def parse_boe_page(text: str, *, name_ar: str) -> ParsedRegulation:
    """``text`` is already-normalized flat text (``grc_regulatory_crawlers.html_to_text``'s
    output) of one BOE law page. ``name_ar`` comes from the regulation catalog entry that led
    here — the page's own Arabic name repeats several times in different contexts (title,
    breadcrumb, body header), none reliably first, so the catalog's own name is trusted
    instead of re-extracting it from the page body."""
    metadata = _extract_metadata(text)

    chapter_matches = list(_CHAPTER_RE.finditer(text))
    sections: list[ParsedSection] = []
    position = 0

    if not chapter_matches:
        # A short regulation with no explicit chapters at all — every article is top-level.
        for code, body in _iter_articles(text):
            clean_text, amendment_note = _split_amendment(body)
            sections.append(
                ParsedSection(
                    section_type="article",
                    code=code,
                    path=(),
                    position=position,
                    text_ar=clean_text or None,
                    amendment_note_ar=amendment_note,
                )
            )
            position += 1
        return ParsedRegulation(
            name_ar=name_ar,
            name_en=metadata["name_en"],
            issuance_date_raw=metadata["issuance_date"],
            publication_date_raw=metadata["publication_date"],
            status_ar=metadata["status"],
            official_citation=metadata["official_citation"],
            sections=tuple(sections),
        )

    for index, chapter_match in enumerate(chapter_matches):
        chapter_code = chapter_match.group(1).strip()
        chapter_title = chapter_match.group(2).strip() or None
        chapter_start = chapter_match.end()
        chapter_end = (
            chapter_matches[index + 1].start() if index + 1 < len(chapter_matches) else len(text)
        )
        chapter_parent_index = len(sections)
        sections.append(
            ParsedSection(
                section_type="chapter",
                code=chapter_code,
                path=(),
                position=position,
                title_ar=chapter_title,
            )
        )
        position += 1

        chapter_body = text[chapter_start:chapter_end]
        for code, body in _iter_articles(chapter_body):
            clean_text, amendment_note = _split_amendment(body)
            sections.append(
                ParsedSection(
                    section_type="article",
                    code=code,
                    path=(chapter_code,),
                    position=position,
                    text_ar=clean_text or None,
                    amendment_note_ar=amendment_note,
                    parent_index=chapter_parent_index,
                )
            )
            position += 1

    return ParsedRegulation(
        name_ar=name_ar,
        name_en=metadata["name_en"],
        issuance_date_raw=metadata["issuance_date"],
        publication_date_raw=metadata["publication_date"],
        status_ar=metadata["status"],
        official_citation=metadata["official_citation"],
        sections=tuple(sections),
    )


def _is_amendment_restatement(text: str, match: re.Match[str]) -> bool:
    """A real BOE page repeats an article's own heading immediately under its
    ``تعديلات المادة`` block (e.g. "...تعديلات المادة\nالمادة الخامسة\nعُدلت..." — restating
    *which* article the amendment note that follows belongs to). That repeat is not a new
    article boundary: it is true exactly when nothing but whitespace separates the nearest
    preceding ``تعديلات المادة`` marker from this heading."""
    preceding = text[: match.start()]
    marker_pos = preceding.rfind(_AMENDMENT_HEADING)
    if marker_pos == -1:
        return False
    return not preceding[marker_pos + len(_AMENDMENT_HEADING) :].strip()


def _iter_articles(text: str) -> list[tuple[str, str]]:
    """Every ``(article_code, article_body)`` pair in ``text``, in order — the ``المادة``
    heading is the hard split boundary; nothing before the first article heading is returned
    (chapter preambles, if any, are not modeled as a section in this phase)."""
    matches = [
        match for match in _ARTICLE_RE.finditer(text) if not _is_amendment_restatement(text, match)
    ]
    results = []
    for index, match in enumerate(matches):
        code = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        results.append((code, text[start:end]))
    return results
