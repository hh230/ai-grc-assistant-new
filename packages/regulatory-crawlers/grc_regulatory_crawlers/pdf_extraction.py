"""PDF text extraction, via ``pypdf`` — the one dependency this package adds beyond the
standard library. A regulator's circulars/regulations are routinely published as PDF, so
extracting their text is required to normalize them into ``RegulatoryDocumentInput``.
"""

from __future__ import annotations

import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .exceptions import CrawlerFetchError


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF's raw bytes, page by page.

    Raises ``CrawlerFetchError`` if the bytes are not a readable PDF, or if extraction
    produced no text at all (e.g. a scanned, image-only PDF with no embedded text layer —
    OCR is out of scope for this phase)."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as exc:
        raise CrawlerFetchError(f"failed to read PDF: {exc}") from exc
    text = "\n".join(pages_text)
    if not text.strip():
        raise CrawlerFetchError("PDF contained no extractable text (scanned/image-only PDF?)")
    return text
