"""Response contracts: required sections/citations/formatting/confidence/forbidden per workflow."""

from __future__ import annotations

from decision_engine import UserRequest
from pipeline_contracts import TenantContext
from prompt_orchestrator import PromptOrchestrator
from prompt_orchestrator.contracts import contract_for
from prompt_orchestrator.models import SegmentKind
from prompt_orchestrator.renderer import render_contract

from tests.conftest import make_context_package, make_plan

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")


def test_confidence_required_for_assertive_workflows():
    for intent in ("compliance_review", "gap_assessment", "risk_analysis", "policy_review"):
        assert contract_for(intent).required_confidence, intent


def test_confidence_not_required_for_lookup():
    assert not contract_for("lookup").required_confidence


def test_citations_required_for_grounded_but_not_conversation():
    assert contract_for("gap_assessment").required_citations
    assert not contract_for("conversation").required_citations


def test_forbidden_outputs_cover_core_guardrails():
    forbidden = contract_for("compliance_review").forbidden_outputs
    assert any("legal advice" in f for f in forbidden)
    assert any("certification" in f for f in forbidden)
    assert any("attest" in f for f in forbidden)


def test_rendered_contract_lists_required_sections():
    contract = contract_for("gap_assessment")
    text = render_contract(contract)
    for section in contract.required_sections:
        assert section in text
    assert "Do NOT produce" in text
    assert "Confidence" in text


def test_contract_reaches_the_prompt_segment():
    req = PromptOrchestrator().orchestrate(make_plan("comparison"), make_context_package(),
                                           UserRequest(tenant=_TENANT, query="compare frameworks"))
    contract_seg = req.segment(SegmentKind.RESPONSE_CONTRACT).content
    assert "Comparison Table" in contract_seg
    assert req.response_contract.workflow == "comparison"


def test_unknown_intent_falls_back_to_a_nonempty_contract():
    contract = contract_for("does_not_exist")
    assert not contract.is_empty()
