"""End-to-end builder behaviour on synthetic input (deterministic, no corpus)."""

from __future__ import annotations

from context_builder import ContextBuilder, WorkflowPolicy
from context_builder.citations import citation_is_complete
from tests.conftest import make_chunk, make_context


def test_full_pipeline_produces_a_valid_structured_package():
    ctx = make_context([
        make_chunk("a", "Access control policy requirements.", document_id="iso", document_profile="iso_standard"),
        make_chunk("a-dup", "Access control policy requirements.", document_id="iso2",
                   document_profile="iso_standard", source_filename="iso2.pdf", score=0.5),
        make_chunk("p", "Corporate access policy statement.", document_id="pol",
                   document_profile="corporate_policy", code=None, heading_path=("Policy",)),
    ], query="access control")
    pkg = ContextBuilder().build(ctx, workflow=WorkflowPolicy.GAP_ASSESSMENT, budget=8000)

    assert pkg.valid
    assert pkg.query == "access control"
    assert pkg.workflow == "gap_assessment"
    assert pkg.sections  # structured, not a string
    assert pkg.metrics.duplicates_removed == 1
    # every block keeps a complete citation
    assert all(citation_is_complete(b.citation) for b in pkg.all_blocks())
    assert pkg.token_count <= pkg.budget.max_tokens


def test_workflow_accepts_intent_string():
    ctx = make_context([make_chunk("a", "text")])
    pkg = ContextBuilder().build(ctx, workflow="compliance_review")
    assert pkg.workflow == "compliance_review"


def test_unknown_workflow_falls_back_to_general():
    pkg = ContextBuilder().build(make_context([make_chunk("a", "text")]), workflow="not_a_workflow")
    assert pkg.workflow == "general"


def test_empty_retrieval_yields_valid_empty_package():
    pkg = ContextBuilder().build(make_context([], warnings=["insufficient evidence"]))
    assert pkg.valid
    assert pkg.sections == []
    assert "insufficient evidence" in pkg.warnings
    assert pkg.metrics.chunks_selected == 0


def test_metrics_are_populated():
    ctx = make_context([make_chunk(f"c{i}", f"distinct clause number {i} about controls", document_id=f"d{i}")
                        for i in range(5)])
    pkg = ContextBuilder().build(ctx, workflow=WorkflowPolicy.EXPLANATION, budget=8000)
    m = pkg.metrics.to_dict()
    assert m["chunks_in"] == 5
    assert m["chunks_selected"] >= 1
    assert m["token_usage"] == pkg.budget.used_tokens
    assert m["remaining_budget"] == pkg.budget.remaining


def test_to_dict_is_json_serializable():
    import json

    ctx = make_context([make_chunk("a", "text")])
    pkg = ContextBuilder().build(ctx)
    json.dumps(pkg.to_dict())  # must not raise
