"""Fallback PDF backend: pypdfium2 (Python bindings for Chromium's PDF engine, PDFium).
More permissive than pypdf — it reads non-conformant-but-complete PDFs that pypdf
rejects. Used only when pypdf raises, so the common path stays on pypdf and only the
harder documents pay pypdfium2's cost.

Same output convention as every other backend: one form-feed (`\\f`) between pages,
`page_count` = the document's page count."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

from knowledge_importer.parsers.base import ParsedText


@dataclass
class PypdfiumBackend:
    name: str = "pypdfium2"

    def extract(self, path: Path) -> ParsedText:
        document = pdfium.PdfDocument(str(path))
        try:
            pages = []
            for index in range(len(document)):
                page = document[index]
                text_page = page.get_textpage()
                pages.append(text_page.get_text_range() or "")
            return ParsedText(text="\f".join(pages), page_count=len(document))
        finally:
            document.close()
