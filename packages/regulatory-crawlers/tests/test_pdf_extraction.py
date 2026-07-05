"""Unit tests for PDF text extraction (pypdf-backed)."""

from __future__ import annotations

import pytest
from grc_regulatory_crawlers import pdf_to_text
from grc_regulatory_crawlers.exceptions import CrawlerFetchError


def _minimal_pdf(text: str) -> bytes:
    """Build a minimal, valid single-page PDF containing `text` as a content stream — enough
    to exercise pypdf's real extraction path without any external fixture file."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects.append(
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += b"trailer\n" + f"<< /Size {count} /Root 1 0 R >>\n".encode()
    out += f"startxref\n{xref_offset}\n".encode()
    out += b"%%EOF"
    return bytes(out)


def test_pdf_to_text_extracts_embedded_text() -> None:
    pdf_bytes = _minimal_pdf("Entities shall encrypt data at rest.")

    text = pdf_to_text(pdf_bytes)

    assert "Entities shall encrypt data at rest." in text


def test_pdf_to_text_rejects_non_pdf_bytes() -> None:
    with pytest.raises(CrawlerFetchError, match="failed to read PDF"):
        pdf_to_text(b"this is not a pdf at all")


def test_pdf_to_text_rejects_a_pdf_with_no_extractable_text() -> None:
    blank_pdf = _minimal_pdf("")
    with pytest.raises(CrawlerFetchError, match="no extractable text"):
        pdf_to_text(blank_pdf)
