"""The flagship structured deliverable: the Gap Matrix (`control ↔ status ↔ evidence`), derived
deterministically from a completed gap-assessment mission + the framework catalog."""

from __future__ import annotations

from deliverables import build_gap_matrix, lexical_coverage, render_gap_matrix_markdown
from framework_library import Control


def test_matrix_marks_covered_vs_gap_controls(gap_mission, library) -> None:
    matrix = build_gap_matrix(gap_mission, library)

    assert matrix.framework == "ISO/IEC 27001:2022"
    assert matrix.scope == "Technological"
    assert matrix.total == 2
    by_code = {r.control_code: r for r in matrix.rows}

    # A.8.5 Secure authentication — evidence mentions "authentication" → covered, with its source
    assert by_code["A.8.5"].covered is True
    assert by_code["A.8.5"].status == "covered"
    assert by_code["A.8.5"].evidence == ("doc-acme-1",)

    # A.8.24 Use of cryptography — no supporting evidence → a gap, no sources
    assert by_code["A.8.24"].covered is False
    assert by_code["A.8.24"].status == "gap"
    assert by_code["A.8.24"].evidence == ()


def test_coverage_headline(gap_mission, library) -> None:
    matrix = build_gap_matrix(gap_mission, library)
    assert matrix.covered_count == 1
    assert matrix.coverage == 0.5
    assert tuple(r.control_code for r in matrix.gaps) == ("A.8.24",)


def test_lexical_coverage_heuristic_is_transparent() -> None:
    control = Control(id="x", code="A.8.5", title="Secure authentication", domain="Technological")
    assert lexical_coverage(control, "we use multi-factor authentication") is True
    assert lexical_coverage(control, "we back up data nightly") is False


def test_a_custom_coverage_classifier_can_be_injected(gap_mission, library) -> None:
    # everything is a gap under a classifier that trusts nothing — proves coverage is pluggable
    matrix = build_gap_matrix(gap_mission, library, coverage=lambda control, text: False)
    assert matrix.covered_count == 0
    assert matrix.coverage == 0.0


def test_renders_a_markdown_table_named_evidence_mapping(gap_mission, library) -> None:
    md = render_gap_matrix_markdown(build_gap_matrix(gap_mission, library))
    # honest naming: this deterministic matrix is evidence mapping, NOT a compliance assessment
    assert "# Gap Matrix — Evidence Mapping (ISO/IEC 27001:2022)" in md
    assert "not a compliance attestation" in md
    assert "1/2 (50%) controls have supporting evidence" in md
    assert "| A.8.5 | Secure authentication | covered | doc-acme-1 |" in md
    assert "| A.8.24 | Use of cryptography | gap | — |" in md
