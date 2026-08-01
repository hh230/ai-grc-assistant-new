"""Concrete Result adapters wiring the frozen Application contracts to the `deliverables` package
(ADR 0054; composition root per ADR 0052). This is the only place `grc-api` imports `deliverables` /
`framework_library`; the Application layer above sees only the ports.

- `BundledDeliverableProvider` — `DeliverableProvider` over `build_deliverable` (the base doc).
- `GenericResultBuilder` — any mission → `GenericContent` from the base Deliverable's sections.
- `GapAssessmentResultBuilder` — **enriches** the base with `build_gap_matrix` →
  `GapAssessmentContent` (does not rebuild sections). Depends on a `FrameworkProvider`, not
  `from_bundled()` directly.
- `Markdown/Docx/Pdf` exporters — render a **`ResultView`** (what the user sees) to bytes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from deliverables import (
    Deliverable,
    Section,
    build_deliverable,
    build_gap_matrix,
    deliverable_to_docx,
    deliverable_to_pdf,
    render_markdown,
)
from mission_application import (
    CoverageView,
    ExportedFile,
    GapAssessmentContent,
    GapRowView,
    GenericContent,
    ResultSectionView,
    ResultView,
)

# --- providers & builders ---------------------------------------------------------------


class BundledDeliverableProvider:
    """`DeliverableProvider`: the base Deliverable for any mission (title from the goal)."""

    def build(self, mission: Any) -> Any:
        return build_deliverable(mission, title=mission.goal)


def _sections(deliverable: Any) -> tuple[ResultSectionView, ...]:
    return tuple(
        ResultSectionView(
            heading=section.heading,
            body=section.body,
            citations=tuple(section.citations),
            confidence=section.confidence,
        )
        for section in deliverable.sections
    )


class GenericResultBuilder:
    """`DeliverableBuilder` for any mission: the base sections, nothing type-specific."""

    def __init__(self, deliverables: Any) -> None:
        self._deliverables = deliverables

    def build_content(self, mission: Any) -> GenericContent:
        return GenericContent(sections=_sections(self._deliverables.build(mission)))


class GapAssessmentResultBuilder:
    """`DeliverableBuilder` for a Gap Assessment: **enriches** the base Deliverable with the gap
    matrix (via the injected `FrameworkProvider`) — it does not rebuild the sections."""

    def __init__(self, deliverables: Any, frameworks: Any) -> None:
        self._deliverables = deliverables
        self._frameworks = frameworks

    def build_content(self, mission: Any) -> GapAssessmentContent:
        base = self._deliverables.build(mission)  # base sections, built once
        matrix = build_gap_matrix(mission, self._frameworks)  # the enrichment
        coverage = CoverageView(
            framework=matrix.framework,
            coverage=matrix.coverage,
            covered_count=matrix.covered_count,
            total=matrix.total,
            gaps=tuple(
                GapRowView(
                    control_code=row.control_code,
                    control_title=row.control_title,
                    covered=row.covered,
                    evidence=tuple(row.evidence),
                )
                for row in matrix.gaps
            ),
        )
        return GapAssessmentContent(sections=_sections(base), coverage=coverage)


# --- exporters (render the ResultView the user sees) ------------------------------------


def _deliverable_of(result: ResultView) -> Any:
    """Map the user-visible `ResultView` back to a `deliverables.Deliverable` so the package's
    renderers can produce the file — export renders the result, not the mission."""
    generated_at = datetime.now(tz=timezone.utc).isoformat()
    return Deliverable(
        title=result.title,
        goal="",
        tenant_id="",
        generated_at=generated_at,
        sections=tuple(
            Section(
                heading=section.heading,
                body=section.body,
                citations=tuple(section.citations),
                confidence=section.confidence,
            )
            for section in result.content.sections
        ),
    )


_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class MarkdownExporter:
    def export(self, result: ResultView) -> ExportedFile:
        content = render_markdown(_deliverable_of(result)).encode("utf-8")
        return ExportedFile(
            content=content, media_type="text/markdown", filename=f"{result.mission_id}.md"
        )


class DocxExporter:
    def export(self, result: ResultView) -> ExportedFile:
        content = deliverable_to_docx(_deliverable_of(result))
        return ExportedFile(content=content, media_type=_DOCX, filename=f"{result.mission_id}.docx")


class PdfExporter:
    def export(self, result: ResultView) -> ExportedFile:
        content = deliverable_to_pdf(_deliverable_of(result))
        return ExportedFile(
            content=content, media_type="application/pdf", filename=f"{result.mission_id}.pdf"
        )
