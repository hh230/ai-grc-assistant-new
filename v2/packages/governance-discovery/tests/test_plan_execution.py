"""ADR 0066 §5: the pure mechanics behind Plan Execution — per-recommendation confidence
(§5.6), `due_at` from timeframe bucket (§3.1), and reversible-by-construction maturity
recalculation via `effective_signals()` (§5.3)."""

from governance_discovery.analysis import analyze
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.execution import effective_signals
from governance_discovery.pack import load_bundled_packs
from governance_discovery.predicate import referenced_signals
from governance_discovery.scheduler import compute_due_at
from governance_discovery.signal import Signal, SignalSet, ValueType

from tests.helpers import make_signals


def _engine() -> DiscoveryEngine:
    return DiscoveryEngine(load_bundled_packs())


def test_referenced_signals_walks_all_any_and_leaves() -> None:
    expr = {
        "all": [
            {"signal": "a", "op": "eq", "value": 1},
            {
                "any": [
                    {"signal": "b", "op": "eq", "value": 2},
                    {"signal": "c", "op": "eq", "value": 3},
                ]
            },
        ]
    }
    assert referenced_signals(expr) == frozenset({"a", "b", "c"})
    assert referenced_signals(None) == frozenset()


def test_every_scheduled_item_carries_confidence_and_source_signal_keys() -> None:
    signals = make_signals(
        primary_activity="legal_services",
        employee_count=5,
        has_compliance_officer=False,
        has_board=False,
        org_structure_state="absent",
        policy_state="absent",
        risk_register_state="absent",
        internal_audit_state="absent",
        has_legal_team=True,
        has_it_team=False,
        execution_capacity="ad_hoc",
        handles_personal_data=False,
        has_gov_clients=False,
    )
    result = analyze(signals, _engine())
    assert result.plan_items  # sanity: this scenario does produce items
    for item in result.plan_items:
        assert isinstance(item["confidence"], float)
        assert 0.0 <= item["confidence"] <= 1.0
        assert isinstance(item["source_signal_keys"], list)


def test_confidence_reflects_direct_answers_fully_when_session_is_complete() -> None:
    """With today's Knowledge Packs (only direct-entry answers) and a fully-answered session,
    confidence should read at (or very near) 100% — the honest baseline before the free-text
    normalizer role introduces real sub-1.0 signal confidences."""
    signals = make_signals(
        primary_activity="legal_services",
        employee_count=5,
        provides_saas=False,
        has_compliance_officer=False,
        has_board=True,
        org_structure_state="approved",
        policy_state="approved",
        risk_register_state="approved",
        internal_audit_state="approved",
        has_legal_team=True,
        has_it_team=True,
        execution_capacity="dedicated_budget",
        handles_personal_data=False,
        has_gov_clients=False,
        last_policy_review_date="2026-01-15",  # policy_state=approved makes this required too
    )
    result = analyze(signals, _engine())
    designate_owner = next(
        i for i in result.plan_items if i["id"] == "seed:designate_compliance_owner"
    )
    assert designate_owner["confidence"] == 1.0
    assert designate_owner["source_signal_keys"] == ["has_compliance_officer"]


def test_lower_signal_confidence_lowers_the_items_it_touches() -> None:
    """A signal with reduced confidence (e.g. the future LLM normalizer's output) must lower the
    confidence of exactly the items whose firing rule reads it — not every item in the plan."""
    engine = _engine()
    low_conf_signal = Signal(
        key="has_compliance_officer", value_type=ValueType.BOOLEAN, value=False, confidence=0.6
    )
    signals = make_signals(
        primary_activity="legal_services",
        employee_count=5,
        has_board=False,
        org_structure_state="absent",
        policy_state="verbal",
    ).with_signal(low_conf_signal)
    result = analyze(signals, engine)
    designate_owner = next(
        i for i in result.plan_items if i["id"] == "seed:designate_compliance_owner"
    )
    formalize = next(i for i in result.plan_items if i["id"] == "seed:formalize_org_structure")
    assert designate_owner["confidence"] < formalize["confidence"]


def test_compute_due_at_matches_the_six_period_timeline() -> None:
    created_at = 1_000_000.0
    assert compute_due_at(created_at, "week_1") == created_at + 7 * 86_400
    assert compute_due_at(created_at, "year_1") == created_at + 365 * 86_400


def test_effective_signals_applies_completed_resolutions_over_baseline() -> None:
    baseline = SignalSet().with_signal(
        Signal(key="risk_register_state", value_type=ValueType.ENUM, value="absent")
    )
    result = effective_signals(baseline, [("risk_register_state", "approved", 100.0)])
    assert result.value("risk_register_state") == "approved"


def test_effective_signals_is_reversible_by_simply_omitting_the_resolution() -> None:
    """The whole point of §5.3: 'un-completing' a task needs no undo logic — it just stops
    contributing to the resolutions list, and the baseline value re-emerges automatically."""
    baseline = SignalSet().with_signal(
        Signal(key="risk_register_state", value_type=ValueType.ENUM, value="absent")
    )
    with_completion = effective_signals(baseline, [("risk_register_state", "approved", 100.0)])
    assert with_completion.value("risk_register_state") == "approved"

    after_reopening = effective_signals(baseline, [])  # the item is no longer in the "done" set
    assert after_reopening.value("risk_register_state") == "absent"


def test_effective_signals_last_completed_wins_on_a_shared_key() -> None:
    baseline = SignalSet()
    result = effective_signals(
        baseline,
        [
            ("risk_register_state", "documented_unapproved", 100.0),
            ("risk_register_state", "approved", 200.0),  # completed later -> wins
        ],
    )
    assert result.value("risk_register_state") == "approved"


def test_resolves_signal_flows_from_pack_data_through_analyze_to_the_scheduled_item() -> None:
    signals = make_signals(primary_activity="legal_services", has_compliance_officer=False)
    result = analyze(signals, _engine())
    designate_owner = next(
        i for i in result.plan_items if i["id"] == "seed:designate_compliance_owner"
    )
    assert designate_owner["resolves_signal"] == {"signal": "has_compliance_officer", "value": True}


def test_effective_signals_never_mutates_the_baseline() -> None:
    baseline = SignalSet().with_signal(
        Signal(key="risk_register_state", value_type=ValueType.ENUM, value="absent")
    )
    effective_signals(baseline, [("risk_register_state", "approved", 100.0)])
    assert baseline.value("risk_register_state") == "absent"  # untouched
