from __future__ import annotations

from decision_engine import DecisionEngine, UserRequest
from pipeline_contracts import TenantContext

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")

ENGINE = DecisionEngine()


def plan(query: str, has_document: bool = False):
    return ENGINE.decide(UserRequest(tenant=_TENANT, query=query, has_document=has_document))


def test_exact_spec_example_matches() -> None:
    p = plan("Compare ISO 27001 with ECC")
    assert p.intent == "comparison"
    assert p.workflow == "comparison_workflow"
    assert p.requires_retrieval is True
    assert p.retrieval_passes == 2
    assert p.requires_reranker is True
    assert p.requires_document is False
    assert p.requires_human_gate is False
    assert p.context_budget == 20
    assert p.target_profiles == ["iso_standard", "control_framework"]


def test_every_intent_maps_to_a_workflow() -> None:
    # exercise a representative query per GRC intent and confirm a workflow is chosen
    samples = {
        "lookup": "what is ISO 27001 A.5.15",
        "explanation": "explain risk management framework",
        "comparison": "compare ISO 27001 with NIST",
        "compliance_review": "are we compliant with PDPL",
        "policy_review": "review our privacy policy",
        "obligation_extraction": "extract obligations from the PDPL",
        "risk_analysis": "risk analysis of the migration",
        "gap_assessment": "gap assessment against NCA ECC",
        "control_mapping": "which control addresses access management",
        "cross_framework_mapping": "map ISO 27001 to NIST CSF",
        "summarization": "summarize NIST 800-53",
        "conversation": "hello",
    }
    for intent, query in samples.items():
        p = plan(query)
        assert p.intent == intent, (query, p.intent)
        assert p.workflow  # non-empty workflow name always chosen


def test_lookup_is_tight_and_skips_reranker() -> None:
    p = plan("what is ISO 27001 clause A.5.15")
    assert p.intent == "lookup"
    assert p.retrieval_passes == 1
    assert p.requires_reranker is False  # confident exact lookup bypasses reranking
    assert p.context_budget == 5


def test_compliance_and_gap_and_risk_require_human_gate() -> None:
    for query in ["are we compliant with PDPL", "gap assessment against NCA ECC", "risk analysis of vendor onboarding"]:
        p = plan(query)
        assert p.requires_human_gate is True, query


def test_lookup_and_comparison_do_not_gate() -> None:
    for query in ["what is ISO 27001 A.5.15", "compare ISO 27001 with NIST CSF"]:
        assert plan(query).requires_human_gate is False, query


def test_document_analysis_uses_attachment_not_corpus() -> None:
    p = plan("analyze this uploaded contract", has_document=True)
    assert p.intent == "document_analysis"
    assert p.requires_document is True
    assert p.requires_retrieval is False
    assert p.retrieval_passes == 0
    assert p.context_budget == 0


def test_summarization_of_attachment_skips_retrieval() -> None:
    p = plan("summarize this document", has_document=True)
    assert p.intent == "summarization"
    assert p.requires_document is True
    assert p.requires_retrieval is False


def test_summarization_of_corpus_source_retrieves() -> None:
    p = plan("summarize NIST SP 800-53")
    assert p.intent == "summarization"
    assert p.requires_retrieval is True
    assert p.retrieval_passes == 1


def test_bare_attachment_defaults_to_document_analysis() -> None:
    p = plan("", has_document=True)
    assert p.intent == "document_analysis"
    assert p.requires_document is True


def test_comparison_passes_scale_with_subjects() -> None:
    two = plan("compare ISO 27001 with NIST CSF")
    three = plan("compare ISO 27001 vs NIST CSF vs COBIT")
    assert two.retrieval_passes == 2
    assert three.retrieval_passes == 3


def test_target_profiles_from_detected_frameworks() -> None:
    p = plan("compare ISO 27001 with NIST CSF")
    assert p.target_profiles == ["iso_standard", "control_framework"]


def test_target_profiles_fall_back_to_workflow_defaults() -> None:
    # obligation extraction with no named framework → law/regulation defaults
    p = plan("extract the obligations")
    assert p.intent == "obligation_extraction"
    assert p.target_profiles == ["law", "regulation"]


def test_multi_step_composite_worked_example() -> None:
    p = plan("compare ISO 27001 with ECC and tell me which controls our policy does not cover")
    assert p.multi_step is True
    # the request legitimately combines a comparison and a gap assessment; either may be the
    # primary, but both must be captured across primary + secondaries
    captured = {p.intent, *p.secondary_intents}
    assert "comparison" in captured
    assert "gap_assessment" in captured
    assert p.requires_human_gate is True  # gap assessment gates
    assert p.retrieval_passes >= 3  # comparison passes + gap passes
    assert p.requires_retrieval is True


def test_cross_framework_promotion_over_control_mapping() -> None:
    p = plan("map the controls in ISO 27001 to NCA ECC")
    assert p.intent == "cross_framework_mapping"


def test_plan_is_deterministic() -> None:
    a = plan("compare ISO 27001 with ECC").to_dict()
    b = plan("compare ISO 27001 with ECC").to_dict()
    assert a == b


def test_every_plan_has_a_reason() -> None:
    for query in ["compare ISO 27001 with ECC", "hello", "what is the weather", "ISO 27001 and policy"]:
        assert plan(query).reason  # explainability is mandatory


def test_engine_builds_the_request_from_a_dict_plus_a_tenant() -> None:
    # The tenant is supplied by the trusted caller, never parsed from the payload (ADR 0040 §3).
    p = ENGINE.decide(
        UserRequest.from_dict({"query": "Compare ISO 27001 with ECC"}, tenant=_TENANT)
    )
    assert p.intent == "comparison"


def test_non_retrieval_plans_have_zero_passes_and_budget() -> None:
    for query in ["hello", "what is the weather"]:
        p = plan(query)
        assert p.requires_retrieval is False
        assert p.retrieval_passes == 0
        assert p.context_budget == 0
