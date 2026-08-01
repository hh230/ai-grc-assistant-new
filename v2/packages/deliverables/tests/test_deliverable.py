"""The generic structured deliverable: any completed mission → sections with provenance, exportable
to audit-ready Markdown."""

from __future__ import annotations

from datetime import datetime, timezone

from deliverables import build_deliverable, render_markdown

_FIXED = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def test_each_step_becomes_a_cited_section(gap_mission) -> None:
    deliverable = build_deliverable(gap_mission, title="Gap Assessment", now=_FIXED)

    assert deliverable.title == "Gap Assessment"
    assert deliverable.goal == "gap assessment: Technological"
    assert deliverable.tenant_id == "org_acme"
    assert deliverable.generated_at == "2026-07-20T12:00:00+00:00"

    headings = [s.heading for s in deliverable.sections]
    assert headings == ["Identify Controls", "Gather Evidence", "Compute Gap"]
    # provenance is carried through: the evidence section cites the customer's document
    evidence_section = deliverable.sections[1]
    assert evidence_section.citations == ("doc-acme-1",)


def test_renders_audit_ready_markdown(gap_mission) -> None:
    md = render_markdown(build_deliverable(gap_mission, title="Gap Assessment", now=_FIXED))
    assert md.startswith("# Gap Assessment\n")
    assert "- **Tenant:** org_acme" in md
    assert "## Identify Controls" in md
    assert "**Sources:** doc-acme-1" in md               # the provenance is exported


def test_serializes_to_a_plain_dict(gap_mission) -> None:
    data = build_deliverable(gap_mission, title="Gap Assessment", now=_FIXED).to_dict()
    assert data["title"] == "Gap Assessment"
    assert isinstance(data["sections"], list) and len(data["sections"]) == 3
