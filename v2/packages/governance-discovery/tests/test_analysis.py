"""Golden-scenario tests for Tier B (`analyze`) — the one-shot, end-of-session analysis pass. Each
scenario traces a full, realistic set of answers through to frameworks/maturity/capacity/gaps/
plan_items, proving the design holds together end-to-end (ADR 0066 §5-equivalent worked examples).
"""

from governance_discovery.analysis import analyze
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.pack import load_bundled_packs
from governance_discovery.scheduler import BUCKET_ORDER

from tests.helpers import make_signals


def _engine() -> DiscoveryEngine:
    return DiscoveryEngine(load_bundled_packs())


def test_multi_pack_composition_a_growing_saas_company() -> None:
    """A technology company that is ALSO a SaaS/cloud provider — both packs contribute frameworks
    simultaneously, proving composability (ADR 0066 §2.1): no single `industry_id` could produce
    this result."""
    signals = make_signals(
        primary_activity="technology",
        provides_saas=True,
        employee_count=15,
        has_compliance_officer=False,
        has_board=False,
        org_structure_state="absent",
        policy_state="absent",
        risk_register_state="absent",
        internal_audit_state="absent",
        has_legal_team=False,
        has_it_team=True,
        execution_capacity="allocated_time",
        handles_personal_data=False,
        has_gov_clients=False,
        tech_team_maturity="documented_unapproved",
        cloud_data_residency_controlled="no",
    )
    result = analyze(signals, _engine())

    framework_ids = {fw["framework_id"] for fw in result.frameworks}
    assert framework_ids == {"framework:iso_27001", "framework:cis", "framework:nist_csf"}

    assert result.confidence == "normal"
    assert result.confidence_score == 1.0
    assert result.gaps == ()

    seed_ids = {item["id"] for item in result.plan_items}
    assert seed_ids == {
        "seed:designate_compliance_owner",
        "seed:establish_governance_oversight_body",
        "seed:formalize_org_structure",
        "seed:draft_foundational_policies",
        "seed:establish_risk_register",
        "seed:implement_data_residency_controls",
        "seed:plan_internal_audit_cadence",
    }

    by_id = {item["id"]: item for item in result.plan_items}
    formalize_idx = BUCKET_ORDER.index(by_id["seed:formalize_org_structure"]["timeframe_bucket"])
    policies_idx = BUCKET_ORDER.index(by_id["seed:draft_foundational_policies"]["timeframe_bucket"])
    assert policies_idx >= formalize_idx  # dependency respected end-to-end

    assert result.capacity["tier"] == "mid"


def test_never_recommends_a_framework_that_is_not_in_the_framework_library() -> None:
    """Handling personal data does NOT invent a PDPL recommendation — no such framework exists in
    the Framework Library yet, and the engine may only ever reference existing `framework_id`s
    (ADR 0066 §2, Alternatives). A generic, un-cited plan seed is produced instead."""
    signals = make_signals(
        primary_activity="legal_services",
        provides_saas=False,
        employee_count=5,
        has_compliance_officer=False,
        org_structure_state="absent",
        policy_state="verbal",
        risk_register_state="absent",
        internal_audit_state="absent",
        has_legal_team=True,
        has_it_team=False,
        execution_capacity="ad_hoc",
        handles_personal_data=True,
        has_gov_clients=True,
    )
    result = analyze(signals, _engine())

    assert result.frameworks == ()  # no pack is active that could name a framework here

    gap_ids = {gap["gap_id"] for gap in result.gaps}
    assert gap_ids == {
        "gap:personal_data_without_policy",
        "gap:gov_client_without_compliance_officer",
    }

    seed_ids = {item["id"] for item in result.plan_items}
    assert "seed:review_personal_data_handling" in seed_ids
    assert "seed:designate_compliance_owner" in seed_ids


def test_sparse_answers_conclude_with_low_confidence_and_a_fail_safe_seed() -> None:
    signals = make_signals(primary_activity="legal_services")
    result = analyze(signals, _engine())

    assert result.confidence == "low"
    assert result.confidence_score < 0.8
    assert [item["id"] for item in result.plan_items] == ["seed:confirm_basics_with_advisor"]


def test_capacity_score_and_tier_reflect_organization_size_and_functions() -> None:
    micro = analyze(make_signals(primary_activity="legal_services", employee_count=3), _engine())
    enterprise = analyze(
        make_signals(
            primary_activity="legal_services",
            employee_count=3000,
            has_legal_team=True,
            has_it_team=True,
            has_compliance_officer=True,
            execution_capacity="dedicated_team_and_budget",
        ),
        _engine(),
    )
    assert micro.capacity["tier"] == "micro"
    assert enterprise.capacity["tier"] == "enterprise"
    ent_budget = enterprise.capacity["per_period_budget"]["week_1"]
    micro_budget = micro.capacity["per_period_budget"]["week_1"]
    assert ent_budget > micro_budget
