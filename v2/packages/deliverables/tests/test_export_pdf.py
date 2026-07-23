"""PDF export — the final downloadable artifact. We build the `.pdf` bytes and read them back with
`pypdf` to assert real, extractable document content (not just that bytes were produced)."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from deliverables import (
    build_deliverable,
    build_gap_matrix,
    deliverable_to_pdf,
    gap_matrix_to_pdf,
)
from pypdf import PdfReader

_FIXED = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_deliverable_pdf_is_a_real_openable_document(gap_mission) -> None:
    data = deliverable_to_pdf(build_deliverable(gap_mission, title="Gap Assessment", now=_FIXED))
    assert data[:5] == b"%PDF-"                              # real PDF file bytes
    text = _pdf_text(data)
    assert "Gap Assessment" in text
    assert "Tenant: org_acme" in text
    assert "Identify Controls" in text
    assert "doc-acme-1" in text                             # provenance exported to the pdf


def test_gap_matrix_pdf_has_the_evidence_table(gap_mission, library) -> None:
    data = gap_matrix_to_pdf(build_gap_matrix(gap_mission, library))
    assert data[:5] == b"%PDF-"
    text = _pdf_text(data)
    assert "Gap Matrix" in text and "Evidence Mapping" in text
    assert "not a compliance attestation" in text          # honest naming in the export
    # the table cells are extractable text
    assert "A.8.5" in text and "Secure authentication" in text and "covered" in text
    assert "A.8.24" in text and "Use of cryptography" in text and "gap" in text
