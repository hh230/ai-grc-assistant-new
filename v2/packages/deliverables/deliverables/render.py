"""Render deliverables to Markdown — an exportable, human-readable, audit-ready document (P3).

Markdown is the portable base format: it displays directly, and a later phase can convert it to DOCX
/ PDF (the `docx`/`pdf` tooling) without changing these builders. Rendering is pure.
"""

from __future__ import annotations

from deliverables.models import Deliverable, GapMatrix


def render_markdown(deliverable: Deliverable) -> str:
    """A structured deliverable as Markdown: a titled document with the goal/tenant/timestamp header
    and one section per step, each carrying its sources (provenance) and confidence."""
    lines: list[str] = [
        f"# {deliverable.title}",
        "",
        f"- **Goal:** {deliverable.goal}",
        f"- **Tenant:** {deliverable.tenant_id}",
        f"- **Generated:** {deliverable.generated_at}",
        "",
    ]
    for section in deliverable.sections:
        lines.append(f"## {section.heading}")
        lines.append("")
        lines.append(section.body or "_(no content)_")
        meta: list[str] = []
        if section.citations:
            meta.append("**Sources:** " + ", ".join(section.citations))
        if section.confidence is not None:
            meta.append(f"**Confidence:** {section.confidence:.2f}")
        if meta:
            lines.append("")
            lines.append(" · ".join(meta))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_gap_matrix_markdown(matrix: GapMatrix) -> str:
    """The Gap Matrix as a Markdown table: `Control | Title | Status | Evidence`, with the headline
    coverage and a gaps summary — the deliverable a customer acts on.

    Titled **Evidence Mapping**, not "assessment", on purpose: the deterministic status is *whether
    supporting evidence was found in the corpus* (a lexical mapping), **not** a compliance
    attestation. The nuanced assessment is the mission's own `compute_gap` synthesis."""
    lines: list[str] = [
        f"# Gap Matrix — Evidence Mapping ({matrix.framework})",
        "",
        f"- **Scope:** {matrix.scope}",
        f"- **Evidence coverage:** {matrix.covered_count}/{matrix.total} "
        f"({matrix.coverage:.0%}) controls have supporting evidence in the corpus",
        f"- **Gaps (no evidence found):** {len(matrix.gaps)}",
        "",
        "_Evidence mapping (lexical) — supporting evidence found, not a compliance attestation._",
        "",
        "| Control | Title | Status | Evidence |",
        "|---|---|---|---|",
    ]
    for row in matrix.rows:
        evidence = ", ".join(row.evidence) if row.evidence else "—"
        lines.append(f"| {row.control_code} | {row.control_title} | {row.status} | {evidence} |")
    return "\n".join(lines) + "\n"
