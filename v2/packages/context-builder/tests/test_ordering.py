"""Ordering & sectioning: per-workflow strategies and within-section order."""

from __future__ import annotations

from context_builder.builder import blocks_from_context
from context_builder.models import BlockRole, WorkflowPolicy
from context_builder.ordering import order_into_sections
from tests.conftest import make_chunk, make_context


def _mixed_blocks():
    # one of each role, distinct documents
    return blocks_from_context(make_context([
        make_chunk("req", "requirement text", document_id="d-iso", document_profile="iso_standard",
                   source_filename="iso.pdf", score=0.6),
        make_chunk("pol", "policy text", document_id="d-pol", document_profile="corporate_policy",
                   source_filename="policy.pdf", code=None, heading_path=("Policy",), score=0.5),
        make_chunk("evi", "evidence text", document_id="d-con", document_profile="contract",
                   source_filename="contract.pdf", code=None, heading_path=("Contract",), score=0.4),
    ]))


def test_gap_assessment_is_requirement_first():
    sections = order_into_sections(_mixed_blocks(), WorkflowPolicy.GAP_ASSESSMENT)
    assert [s.role for s in sections][0] == BlockRole.REQUIREMENT


def test_compliance_review_is_evidence_first():
    sections = order_into_sections(_mixed_blocks(), WorkflowPolicy.COMPLIANCE_REVIEW)
    assert sections[0].role == BlockRole.EVIDENCE


def test_policy_review_is_policy_then_regulation():
    roles = [s.role for s in order_into_sections(_mixed_blocks(), WorkflowPolicy.POLICY_REVIEW)]
    assert roles.index(BlockRole.POLICY) < roles.index(BlockRole.REQUIREMENT)


def test_lookup_is_a_single_smallest_section():
    blocks = blocks_from_context(make_context([
        make_chunk(f"c{i}", f"text {i}", document_id=f"d{i}", score=1.0 - i * 0.1) for i in range(6)
    ]))
    sections = order_into_sections(blocks, WorkflowPolicy.LOOKUP)
    assert len(sections) == 1
    assert sections[0].title == "Answer Context"
    assert len(sections[0].blocks) == 3  # max_blocks cap


def test_comparison_splits_into_two_sides():
    blocks = blocks_from_context(make_context([
        make_chunk("a1", "nist a", document_id="nist", source_filename="nist.pdf", score=0.9),
        make_chunk("a2", "nist b", document_id="nist", source_filename="nist.pdf", score=0.8, code="AC-2"),
        make_chunk("b1", "iso a", document_id="iso", source_filename="iso.pdf", score=0.85),
    ]))
    sections = order_into_sections(blocks, WorkflowPolicy.COMPARISON)
    titles = [s.title for s in sections]
    assert "nist.pdf" in titles and "iso.pdf" in titles


def test_document_analysis_is_attachment_only():
    blocks = blocks_from_context(make_context([
        make_chunk("att", "attached doc clause", document_id="attach", source_filename="upload.pdf", score=0.5),
        make_chunk("other", "unrelated corpus doc", document_id="corpus", source_filename="iso.pdf", score=0.9),
    ]))
    sections = order_into_sections(blocks, WorkflowPolicy.DOCUMENT_ANALYSIS, attachment_document_ids=("attach",))
    kept_docs = {b.document_id for s in sections for b in s.blocks}
    assert kept_docs == {"attach"}


def test_within_section_order_is_by_score_then_reading_order():
    blocks = blocks_from_context(make_context([
        make_chunk("low", "low score", document_id="d", code="A.2", heading_path=("H", "A.2"), page_start=5, score=0.3),
        make_chunk("high", "high score", document_id="d", code="A.1", heading_path=("H", "A.1"), page_start=2, score=0.9),
    ]))
    sections = order_into_sections(blocks, WorkflowPolicy.GENERAL)
    ordered_ids = [b.block_id for s in sections for b in s.blocks]
    assert ordered_ids == ["high", "low"]
