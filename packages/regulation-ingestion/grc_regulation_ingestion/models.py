"""One row of the Saudi Regulations index catalog — a regulation's name and the official
government page it links to (Knowledge Intelligence KI-P6, ADR-0030)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegulationCatalogEntry:
    """``name_ar`` and ``category`` come straight from the index PDF's own bullet text and
    section heading; ``source_url`` is the real hyperlink attached to that bullet (a PDF
    ``/Annots`` link annotation, not visible in the PDF's plain text stream) — never a guess."""

    name_ar: str
    category: str
    source_url: str
