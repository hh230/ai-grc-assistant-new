"""Unit tests for the regulation index PDF catalog extractor: pairing a bulleted regulation
name with its real `/Annots` link annotation (never visible in the PDF's own text stream),
category-heading tracking, and graceful handling of a bullet with no matching link. A hand-
built minimal PDF (with a real link annotation object), not a fixture file or a mock —
matching this repo's `test_pdf_extraction.py` convention.

Bullet/category text here is plain ASCII, not Arabic: a hand-assembled minimal PDF's content
stream uses the base-14 Helvetica font with no embedded CID/ToUnicode mapping, so it cannot
render (and pypdf cannot extract) real Arabic glyphs — that limitation is about this test's
synthetic PDF, not about the extractor, which is Unicode-agnostic (it only looks for a "•"
prefix and a trailing ":"/"："). Real Arabic bullet/link pairing is verified against the actual
live index PDF in the KI-P6 live-verification pass, not here."""

from __future__ import annotations

from grc_regulation_ingestion_adapters import parse_regulation_index


def _minimal_pdf_with_link(
    *, category: str, bullet_text: str, uri: str, extra_bullet: str | None = None
) -> bytes:
    """A single-page PDF whose content stream renders a category heading and one (or two)
    bulleted lines, with one real `/Subtype /Link` annotation (pointing at `uri`) placed over
    the first bullet's line — enough to exercise the real annotation-reading code path."""
    lines = [category, f"• {bullet_text}"]
    if extra_bullet is not None:
        lines.append(f"• {extra_bullet}")

    content_ops = []
    y = 150
    for line in lines:
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        # cp1252 (WinAnsi's byte values), decoded back via the font's own /Encoding below —
        # plain latin-1 has no code point for "•" at all.
        content_ops.append(f"BT /F1 12 Tf 10 {y} Td ({escaped}) Tj ET")
        y -= 20
    stream = "\n".join(content_ops).encode("cp1252", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> /Annots [6 0 R] >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Annot /Subtype /Link /Rect [10 128 190 142] "
        b"/A << /Type /Action /S /URI /URI (" + uri.encode("latin-1") + b") >> >>",
    ]

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


def test_pairs_a_bulleted_regulation_with_its_real_link_and_category() -> None:
    pdf_bytes = _minimal_pdf_with_link(
        category="Basic Systems:",
        bullet_text="Basic Law of Governance",
        uri="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/abc/1",
    )

    entries = parse_regulation_index(pdf_bytes)

    assert len(entries) == 1
    assert entries[0].name_ar == "Basic Law of Governance"
    assert entries[0].category == "Basic Systems"
    assert entries[0].source_url == "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/abc/1"


def test_a_bullet_with_no_matching_link_is_skipped_not_mispaired() -> None:
    pdf_bytes = _minimal_pdf_with_link(
        category="Basic Systems:",
        bullet_text="First Law",
        uri="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/abc/1",
        extra_bullet="Second Law With No Link",
    )

    entries = parse_regulation_index(pdf_bytes)

    # Only one real link annotation exists, for the first bullet; the second bullet must not
    # be silently paired with a leftover/duplicate link.
    assert len(entries) == 1
    assert entries[0].name_ar == "First Law"


def test_rejects_bytes_that_are_not_a_real_pdf() -> None:
    import pytest
    from grc_regulatory_crawlers import CrawlerFetchError

    with pytest.raises(CrawlerFetchError, match="failed to read"):
        parse_regulation_index(b"not a pdf at all")
