"""The Intent Registry — the single source of truth for per-intent behaviour.

Every engine reads this registry instead of keeping a private intent table, so a hole here
(a missing spec, a contract that forgets citations, a lookup that silently mis-resolves)
propagates to routing, context, prompting, and generation at once. It is tested directly.
"""

from __future__ import annotations

from pipeline_contracts import (
    INTENT_REGISTRY,
    ORDERING_POLICIES,
    BlockRole,
    Intent,
    IntentSpec,
    OutputProfile,
    RoutingPolicy,
    WorkflowPolicy,
    spec_for,
)
from pipeline_contracts.intent_registry import CITATION_STYLE


# ── completeness ──────────────────────────────────────────────────────────────
def test_every_intent_has_a_spec():
    """Adding an `Intent` without its spec would fall back to LOOKUP's routing and contract
    — a silent mis-route rather than a failure. The registry must cover the enum."""
    assert set(INTENT_REGISTRY) == set(Intent)


def test_every_spec_is_complete_and_self_consistent():
    for intent, spec in INTENT_REGISTRY.items():
        assert isinstance(spec, IntentSpec)
        assert spec.intent is intent                       # no copy-paste mismatch
        assert isinstance(spec.routing, RoutingPolicy)
        assert isinstance(spec.output_profile, OutputProfile)
        assert spec.routing.name.endswith("_workflow")
        assert spec.template_body.startswith("TASK — ")
        assert spec.response_contract.workflow == intent.value
        assert spec.response_contract.required_sections


def test_every_context_policy_resolves_to_an_ordering_policy():
    for spec in INTENT_REGISTRY.values():
        assert spec.context_policy in ORDERING_POLICIES
        assert spec.ordering is ORDERING_POLICIES[spec.context_policy]


# ── lookups ───────────────────────────────────────────────────────────────────
def test_spec_for_accepts_the_enum_and_its_string_value():
    assert spec_for(Intent.RISK_ANALYSIS) is INTENT_REGISTRY[Intent.RISK_ANALYSIS]
    assert spec_for("risk_analysis") is INTENT_REGISTRY[Intent.RISK_ANALYSIS]


def test_spec_for_falls_back_to_lookup_for_unknown_values():
    """The historic contract/template fallback: an unrecognised intent still answers,
    conservatively, rather than raising into the caller's face."""
    assert spec_for("not_a_real_intent") is INTENT_REGISTRY[Intent.LOOKUP]
    assert spec_for("") is INTENT_REGISTRY[Intent.LOOKUP]


# ── routing ───────────────────────────────────────────────────────────────────
def test_the_non_retrieval_intents_are_exactly_the_ones_that_need_no_evidence():
    ungrounded = {i for i, s in INTENT_REGISTRY.items() if not s.routing.requires_retrieval}
    assert ungrounded == {
        Intent.DOCUMENT_ANALYSIS,  # grounds on the attachment, not the corpus
        Intent.CONVERSATION,
        Intent.AMBIGUOUS,
        Intent.UNSUPPORTED,
    }


def test_intents_that_need_no_retrieval_budget_nothing_for_it():
    for spec in INTENT_REGISTRY.values():
        if not spec.routing.requires_retrieval:
            assert spec.routing.retrieval_passes == 0
            assert spec.routing.context_budget == 0
        else:
            assert spec.routing.retrieval_passes >= 1
            assert spec.routing.context_budget > 0


def test_the_consequential_intents_demand_a_human_gate():
    """CLAUDE.md §3/§9: an assessment a customer could act on is proposed, never applied."""
    gated = {i for i, s in INTENT_REGISTRY.items() if s.routing.requires_human_gate}
    assert gated == {Intent.COMPLIANCE_REVIEW, Intent.RISK_ANALYSIS, Intent.GAP_ASSESSMENT}


def test_document_analysis_is_the_only_intent_requiring_an_attachment():
    requiring = {i for i, s in INTENT_REGISTRY.items() if s.routing.requires_document}
    assert requiring == {Intent.DOCUMENT_ANALYSIS}


# ── response contracts ────────────────────────────────────────────────────────
def test_grounded_intents_require_citations_and_forbid_uncited_claims():
    contract = INTENT_REGISTRY[Intent.COMPLIANCE_REVIEW].response_contract
    assert contract.required_citations is True
    assert contract.citation_style == CITATION_STYLE
    assert "Citations" in contract.required_sections
    assert "uncited factual GRC claims" in contract.forbidden_outputs
    assert "legal advice" in contract.forbidden_outputs


def test_every_citing_contract_ends_with_a_citations_section():
    for spec in INTENT_REGISTRY.values():
        if spec.response_contract.required_citations:
            assert spec.response_contract.required_sections[-1] == "Citations"


def test_the_non_answer_intents_neither_cite_nor_carry_a_citation_style():
    """Conversation, clarification, and refusal make no factual GRC claims, so demanding a
    citation of them would be incoherent."""
    for intent in (Intent.CONVERSATION, Intent.AMBIGUOUS, Intent.UNSUPPORTED):
        contract = INTENT_REGISTRY[intent].response_contract
        assert contract.required_citations is False
        assert contract.citation_style == ""
        assert "Citations" not in contract.required_sections


def test_the_judgement_intents_must_state_a_confidence():
    confident = {i for i, s in INTENT_REGISTRY.items() if s.response_contract.required_confidence}
    assert confident == {
        Intent.COMPLIANCE_REVIEW, Intent.POLICY_REVIEW, Intent.RISK_ANALYSIS, Intent.GAP_ASSESSMENT,
    }


def test_the_intents_that_could_bind_a_customer_forbid_self_authorisation():
    compliance = INTENT_REGISTRY[Intent.COMPLIANCE_REVIEW].response_contract
    risk = INTENT_REGISTRY[Intent.RISK_ANALYSIS].response_contract
    assert "approving or attesting controls on the user's behalf" in compliance.forbidden_outputs
    assert "accepting or signing off risk on the user's behalf" in risk.forbidden_outputs


def test_ambiguous_must_not_answer_before_it_clarifies():
    contract = INTENT_REGISTRY[Intent.AMBIGUOUS].response_contract
    assert "answering before the request is clarified" in contract.forbidden_outputs


# ── context / ordering policies ───────────────────────────────────────────────
def test_context_policy_maps_intents_by_value_and_defaults_to_general():
    assert INTENT_REGISTRY[Intent.LOOKUP].context_policy is WorkflowPolicy.LOOKUP
    # an intent with no same-named policy falls back rather than raising
    assert INTENT_REGISTRY[Intent.RISK_ANALYSIS].context_policy is WorkflowPolicy.GENERAL


def test_ordering_leads_with_the_role_each_workflow_reasons_from():
    assert ORDERING_POLICIES[WorkflowPolicy.GAP_ASSESSMENT].role_order[0] is BlockRole.REQUIREMENT
    assert ORDERING_POLICIES[WorkflowPolicy.COMPLIANCE_REVIEW].role_order[0] is BlockRole.EVIDENCE
    assert ORDERING_POLICIES[WorkflowPolicy.POLICY_REVIEW].role_order[0] is BlockRole.POLICY


def test_every_ordering_policy_covers_every_role():
    """A role missing from an order would silently drop that context from the prompt."""
    for policy in ORDERING_POLICIES.values():
        assert set(policy.role_order) == set(BlockRole)


def test_lookup_keeps_the_smallest_possible_context():
    policy = ORDERING_POLICIES[WorkflowPolicy.LOOKUP]
    assert policy.single_section is True
    assert policy.max_blocks == 3


def test_comparison_splits_by_document_and_balances_the_budget():
    policy = ORDERING_POLICIES[WorkflowPolicy.COMPARISON]
    assert policy.split_by_document is True
    assert policy.balanced is True


def test_document_analysis_reads_only_the_attachment():
    policy = ORDERING_POLICIES[WorkflowPolicy.DOCUMENT_ANALYSIS]
    assert policy.attachment_only is True
    assert policy.single_section is True


# ── output profiles ───────────────────────────────────────────────────────────
def test_analytical_intents_get_the_larger_output_allowance():
    lookup = INTENT_REGISTRY[Intent.LOOKUP].output_profile
    gap = INTENT_REGISTRY[Intent.GAP_ASSESSMENT].output_profile
    assert gap.max_output_tokens > lookup.max_output_tokens


def test_every_output_profile_stays_low_temperature():
    """GRC answers are graded on fidelity to the sources, not on creativity."""
    for spec in INTENT_REGISTRY.values():
        assert spec.output_profile.temperature <= 0.2
        assert spec.output_profile.max_output_tokens > 0


# ── default profiles ──────────────────────────────────────────────────────────
def test_default_profiles_are_declared_only_where_the_intent_has_a_natural_corpus():
    assert INTENT_REGISTRY[Intent.POLICY_REVIEW].routing.default_profiles == ("corporate_policy",)
    assert INTENT_REGISTRY[Intent.OBLIGATION_EXTRACTION].routing.default_profiles == ("law", "regulation")
    # a gap assessment spans everything, so it pins nothing
    assert INTENT_REGISTRY[Intent.GAP_ASSESSMENT].routing.default_profiles == ()
