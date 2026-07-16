"""Context + citation preservation, and missing / invalid context handling."""

from __future__ import annotations

from dataclasses import replace

from decision_engine import UserRequest
from pipeline_contracts import TenantContext
from prompt_orchestrator import PromptOrchestrator
from prompt_orchestrator.models import SegmentKind

from tests.conftest import make_context_package, make_plan

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")


def test_every_citation_reaches_the_prompt():
    pkg = make_context_package(n=5)
    req = PromptOrchestrator().orchestrate(make_plan("gap_assessment"), pkg,
                                           UserRequest(tenant=_TENANT, query="access control"))
    context = req.segment(SegmentKind.CONTEXT).content
    # one marker per block, and every source string present
    for block in pkg.all_blocks():
        assert block.citation.formatted in context
    assert context.count("[S") >= len(pkg.all_blocks())
    assert req.valid


def test_context_blocks_and_markers_match_count():
    pkg = make_context_package(n=4)
    req = PromptOrchestrator().orchestrate(make_plan("compliance_review"), pkg,
                                           UserRequest(tenant=_TENANT, query="assess controls"))
    context = req.segment(SegmentKind.CONTEXT).content
    markers = [ln for ln in context.splitlines() if ln.startswith("[S")]
    # markers appear in both the body and the Sources legend → 2× block count
    assert len(markers) == 2 * len(pkg.all_blocks())


def test_missing_context_is_valid_with_insufficient_evidence():
    # retrieval-required workflow, but no evidence found
    empty = make_context_package(n=0)
    req = PromptOrchestrator().orchestrate(make_plan("gap_assessment"), empty,
                                           UserRequest(tenant=_TENANT, query="obscure control with no evidence"))
    assert req.valid
    assert "No supporting evidence" in req.segment(SegmentKind.CONTEXT).content
    assert any("insufficient-evidence" in w for w in req.warnings)


def test_none_context_for_retrieval_workflow_still_renders_evidence_notice():
    req = PromptOrchestrator().orchestrate(make_plan("lookup", requires_retrieval=True), None,
                                           UserRequest(tenant=_TENANT, query="access control"))
    assert req.valid
    assert req.segment(SegmentKind.CONTEXT) is not None
    assert "No supporting evidence" in req.segment(SegmentKind.CONTEXT).content


def test_invalid_context_is_rejected():
    pkg = make_context_package(n=3)
    pkg.valid = False  # simulate a ContextPackage that failed the builder's validation
    req = PromptOrchestrator().orchestrate(make_plan("gap_assessment"), pkg,
                                           UserRequest(tenant=_TENANT, query="access control"))
    assert not req.valid
    assert any("context package is invalid" in w for w in req.warnings)


def test_lost_citation_is_detected():
    # tamper: give one block an incomplete citation after building
    pkg = make_context_package(n=3)
    block = pkg.sections[0].blocks[0]
    block.citation = replace(block.citation, source_filename="")
    req = PromptOrchestrator().orchestrate(make_plan("gap_assessment"), pkg,
                                           UserRequest(tenant=_TENANT, query="access control"))
    assert not req.valid
    assert any("citation lost" in w for w in req.warnings)
