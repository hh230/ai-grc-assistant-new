from governance_discovery.engine import DiscoveryEngine, DiscoverySessionState
from governance_discovery.pack import load_bundled_packs
from governance_discovery.signal import SignalSet

from tests.helpers import make_signals


def _engine() -> DiscoveryEngine:
    return DiscoveryEngine(load_bundled_packs())


def test_only_core_is_active_before_any_answer() -> None:
    engine = _engine()
    active_ids = {p.pack_id for p in engine.active_packs(SignalSet())}
    assert active_ids == {"pack:core"}


def test_first_question_is_the_primary_activity_dropdown() -> None:
    engine = _engine()
    state = DiscoverySessionState(signals=SignalSet())
    question = engine.next_question(state)
    assert question is not None
    assert question.id == "q:primary_activity"


def test_answering_primary_activity_activates_technology_pack_only() -> None:
    engine = _engine()
    signals = make_signals(primary_activity="technology")
    active_ids = {p.pack_id for p in engine.active_packs(signals)}
    assert active_ids == {"pack:core", "pack:technology"}


def test_answering_provides_saas_activates_cloud_provider_too() -> None:
    """The whole point of composable Knowledge Packs (ADR 0066 §2.1): a company that is BOTH a
    technology company AND a SaaS/cloud provider has both packs active simultaneously — never
    just one `industry_id`."""
    engine = _engine()
    signals = make_signals(primary_activity="technology", provides_saas=True)
    active_ids = {p.pack_id for p in engine.active_packs(signals)}
    assert active_ids == {"pack:core", "pack:technology", "pack:cloud_provider"}


def test_tech_team_maturity_question_only_eligible_once_technology_pack_active() -> None:
    engine = _engine()
    state_before = DiscoverySessionState(
        signals=SignalSet(), answered_question_ids=frozenset({"q:primary_activity"})
    )
    eligible_before = {q.id for q in engine.eligible_questions(state_before)}
    # no primary_activity signal yet -> pack inactive
    assert "q:tech_team_maturity" not in eligible_before

    state_after = DiscoverySessionState(
        signals=make_signals(primary_activity="technology"),
        answered_question_ids=frozenset({"q:primary_activity"}),
    )
    eligible_after = {q.id for q in engine.eligible_questions(state_after)}
    assert "q:tech_team_maturity" in eligible_after


def test_reanswering_primary_activity_reroutes_without_a_separate_algorithm() -> None:
    """Editing an earlier answer just recomputes live state — a non-technology org loses access
    to the technology-specific question (ADR 0066 §2.4)."""
    engine = _engine()
    state = DiscoverySessionState(signals=make_signals(primary_activity="legal_services"))
    eligible = {q.id for q in engine.eligible_questions(state)}
    assert "q:tech_team_maturity" not in eligible


def test_is_concluded_false_while_required_questions_remain() -> None:
    engine = _engine()
    state = DiscoverySessionState(signals=make_signals(primary_activity="legal_services"))
    assert engine.is_concluded(state) is False


def test_is_concluded_true_once_every_required_question_across_active_packs_is_answered() -> None:
    engine = _engine()
    signals = make_signals(
        primary_activity="technology",
        provides_saas=True,
        employee_count=15,
        has_compliance_officer=True,
        has_board=True,
        org_structure_state="approved",
        policy_state="approved",
        risk_register_state="approved",
        has_legal_team=True,
        has_it_team=True,
        execution_capacity="dedicated_budget",
        handles_personal_data=False,
        tech_team_maturity="approved",
        cloud_data_residency_controlled="yes",
        last_policy_review_date="2026-01-15",  # policy_state=approved makes this eligible+required
        ownership_type="private",
        outsources_critical_functions=False,
        operates_critical_infrastructure=False,
        data_geography="ksa_only",
    )
    answered = frozenset(
        {
            "q:primary_activity",
            "q:provides_saas",
            "q:employee_count",
            "q:has_compliance_officer",
            "q:has_board",
            "q:org_structure_state",
            "q:policy_state",
            "q:risk_register_state",
            "q:has_legal_team",
            "q:has_it_team",
            "q:execution_capacity",
            "q:handles_personal_data",
            "q:tech_team_maturity",
            "q:cloud_data_residency_controlled",
            "q:last_policy_review_date",
            "q:ownership_type",
            "q:outsources_critical_functions",
            # Both are in scope for this organization: technology is a plausible
            # critical-infrastructure sector, and it has an IT team, so data location matters.
            "q:operates_critical_infrastructure",
            "q:data_geography",
        }
    )
    state = DiscoverySessionState(signals=signals, answered_question_ids=answered)
    assert engine.is_concluded(state) is True

    answered_count, total_required = engine.required_question_coverage(signals)
    assert answered_count == total_required  # every required question across active packs answered
