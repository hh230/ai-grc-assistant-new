"""Rasheed V2 Deliverables (product roadmap P3) — turn a completed Mission into a **structured,
exportable, audit-ready** GRC deliverable.

- `build_deliverable(mission, title=…)` → a generic `Deliverable` (sections + provenance), for any
  capability; `render_markdown(deliverable)` exports it.
- `build_gap_matrix(mission, library)` → the flagship `GapMatrix` (`control ↔ status ↔ evidence`,
  derived deterministically from the mission + framework catalog); with its markdown renderer.

Pure transformation: consumes `mission-engine` + `framework-library`; no LLM, no Core change.
"""

from deliverables.build import (
    build_deliverable,
    build_gap_matrix,
    lexical_coverage,
)
from deliverables.export import (
    deliverable_to_docx,
    deliverable_to_pdf,
    gap_matrix_to_docx,
    gap_matrix_to_pdf,
)
from deliverables.models import Deliverable, GapMatrix, GapRow, Section
from deliverables.render import render_gap_matrix_markdown, render_markdown

__all__ = [
    "Deliverable",
    "Section",
    "GapMatrix",
    "GapRow",
    "build_deliverable",
    "build_gap_matrix",
    "lexical_coverage",
    "render_markdown",
    "render_gap_matrix_markdown",
    "deliverable_to_docx",
    "gap_matrix_to_docx",
    "deliverable_to_pdf",
    "gap_matrix_to_pdf",
]
