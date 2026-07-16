"""The contract for one PDF extraction engine. A backend does exactly one thing:
extract text from a PDF, preserving the pipeline's page-break convention (one form-feed
`\\f` between pages) and reporting a page count. `PdfParser` (see `../pdf_parser.py`)
holds an ordered list of these and tries each in turn.

Adding a new engine — a third PDF library, or an OCR engine for scanned PDFs — means
implementing this one method and adding the backend to the chain. Nothing else in the
parser, the stage, or the pipeline changes."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from knowledge_importer.parsers.base import ParsedText


class PdfBackend(Protocol):
    name: str

    def extract(self, path: Path) -> ParsedText: ...
