"""Primary PDF backend: pypdf. Fast and correct for the large majority of the library.
It raises on some non-conformant-but-readable PDFs (e.g. files whose generator used
newlines where the spec expects spaces, which trips pypdf's trailer/xref scanner) — for
those, the chain falls through to `pypdfium_backend`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from knowledge_importer.parsers.base import ParsedText


@dataclass
class PypdfBackend:
    name: str = "pypdf"

    def extract(self, path: Path) -> ParsedText:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return ParsedText(text="\f".join(pages), page_count=len(pages))
