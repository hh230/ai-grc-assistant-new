"""Extracts the Saudi Regulations index catalog from the Google Drive PDF (Knowledge
Intelligence KI-P6, ADR-0030): every bulleted regulation name, its category heading, and the
*real* hyperlink attached to it — a PDF ``/Annots`` link annotation, never visible in the
PDF's plain text stream (confirmed live: the index's own extracted text has no URLs at all;
every one of its 479 real links to ``laws.boe.gov.sa`` lives only in the annotation layer).

Text-to-link pairing is a documented best-effort heuristic, not a geometric/positional
match: candidate regulation lines (bulleted with "•") and link annotations (deduplicated
where a wrapped title produces more than one annotation for the same target, then ordered
top-to-bottom by their `/Rect` y-coordinate) are paired strictly in reading order. This holds
for the real index file's own layout (one hyperlinked bullet per regulation, checked against
the live document) but is not a formal PDF layout parser.
"""

from __future__ import annotations

import io
import re

import pypdf
from grc_regulation_ingestion import RegulationCatalogEntry
from grc_regulatory_crawlers import CrawlerFetchError, HttpFetcher

_BULLET_RE = re.compile(r"^[••]\s*(.+)$")
_CATEGORY_RE = re.compile(r"^(.+?)[:：]\s*$")

DEFAULT_USER_AGENT = (
    "AIGRCAssistant-RegulationIngestion/1.0 "
    "(+autonomous-regulation-ingestion; no aggressive crawling; robots.txt honored)"
)


def _ordered_unique_links(page: pypdf.PageObject) -> list[str]:
    """Every real `/Subtype /Link` annotation's URI on this page, top-to-bottom, with
    consecutive duplicates (a single wrapped title spanning more than one line/rect) collapsed
    to one entry."""
    annots = page.get("/Annots")
    if not annots:
        return []
    positioned: list[tuple[float, str]] = []
    for annot in annots:
        obj = annot.get_object()
        if obj.get("/Subtype") != "/Link":
            continue
        action = obj.get("/A")
        uri = action.get("/URI") if action else None
        rect = obj.get("/Rect")
        if uri and rect:
            positioned.append((float(rect[1]), str(uri)))
    positioned.sort(key=lambda entry: entry[0], reverse=True)  # higher y0 = higher on the page

    deduped: list[str] = []
    for _, uri in positioned:
        if not deduped or deduped[-1] != uri:
            deduped.append(uri)
    return deduped


def parse_regulation_index(pdf_bytes: bytes) -> tuple[RegulationCatalogEntry, ...]:
    """Pure parsing of already-fetched PDF bytes — no network here, so this is directly
    testable against a hand-built minimal PDF."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    except Exception as exc:  # noqa: BLE001 - a corrupt/non-PDF download is a clear failure
        raise CrawlerFetchError(f"failed to read the regulation index PDF: {exc}") from exc

    entries: list[RegulationCatalogEntry] = []
    current_category = ""
    for page in reader.pages:
        raw_text = page.extract_text() or ""
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        link_iterator = iter(_ordered_unique_links(page))

        for line in lines:
            bullet_match = _BULLET_RE.match(line)
            if bullet_match is None:
                category_match = _CATEGORY_RE.match(line)
                if category_match is not None:
                    current_category = category_match.group(1).strip()
                continue  # preamble/instructions/other non-bulleted text: never consumes a link

            try:
                source_url = next(link_iterator)
            except StopIteration:
                continue  # more bulleted lines than links on this page: skip, don't mispair
            entries.append(
                RegulationCatalogEntry(
                    name_ar=bullet_match.group(1).strip(),
                    category=current_category,
                    source_url=source_url,
                )
            )
    return tuple(entries)


class DriveIndexCatalogSource:
    """Downloads the index PDF from Google Drive (the direct-download URL form, confirmed
    live) and parses it. A single, occasional fetch of one admin-provided file — not a broad
    crawl — so this does not apply the BOE parser's robots/rate-limiting politeness."""

    def __init__(
        self, fetcher: HttpFetcher, *, file_id: str, user_agent: str = DEFAULT_USER_AGENT
    ) -> None:
        self._fetcher = fetcher
        self._file_id = file_id
        self._user_agent = user_agent

    async def load(self) -> tuple[RegulationCatalogEntry, ...]:
        url = f"https://drive.google.com/uc?export=download&id={self._file_id}"
        response = await self._fetcher.get(url, user_agent=self._user_agent)
        return parse_regulation_index(response.body)
