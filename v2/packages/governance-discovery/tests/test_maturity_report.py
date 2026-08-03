"""The report-facing maturity model (ADR 0066 §4): star + label together (never stars alone),
five dimensions including the new Leadership one, and a deterministic "if the plan is fully
executed" vision projection — all still just data-driven rule evaluation, no LLM involved."""

from governance_discovery.analysis import (
    MATURITY_DIMENSIONS,
    MATURITY_LABELS_BY_STAR,
    analyze,
    stars_and_label,
)
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.pack import load_bundled_packs
from tests.helpers import make_signals


def _engine() -> DiscoveryEngine:
    return DiscoveryEngine(load_bundled_packs())


def test_five_report_facing_dimensions() -> None:
    assert MATURITY_DIMENSIONS == ("governance", "risk", "compliance", "cyber", "leadership")


def test_stars_and_label_are_paired_and_bounded() -> None:
    assert stars_and_label(0) == (0, "none")
    assert stars_and_label(4) == (2, "initial")
    assert stars_and_label(10) == (5, "optimized")
    assert stars_and_label(999) == (5, "optimized")  # clamped, never overflows the scale


def test_every_maturity_entry_carries_score_stars_and_label() -> None:
    signals = make_signals(primary_activity="legal_services", org_structure_state="approved")
    result = analyze(signals, _engine())
    for dim in MATURITY_DIMENSIONS:
        entry = result.maturity[dim]
        assert set(entry) == {"score", "stars", "label"}
        assert entry["label"] in MATURITY_LABELS_BY_STAR


def test_leadership_dimension_scores_from_board_and_compliance_officer() -> None:
    weak = analyze(
        make_signals(primary_activity="legal_services", has_board=False, has_compliance_officer=False),
        _engine(),
    )
    strong = analyze(
        make_signals(
            primary_activity="legal_services",
            has_board=True,
            has_compliance_officer=True,
            execution_capacity="dedicated_team_and_budget",
        ),
        _engine(),
    )
    assert strong.maturity["leadership"]["score"] > weak.maturity["leadership"]["score"]
    assert weak.maturity["leadership"]["stars"] == 0


def test_missing_board_seeds_a_governance_oversight_body_item() -> None:
    result = analyze(make_signals(primary_activity="legal_services", has_board=False), _engine())
    seed_ids = {item["id"] for item in result.plan_items}
    assert "seed:establish_governance_oversight_body" in seed_ids


def test_governance_vision_is_never_lower_than_current_maturity() -> None:
    """The 'if fully executed' projection can only improve on today — it never regresses, and it
    upgrades a currently-weak dimension when the underlying signals are on the maturity scale."""
    signals = make_signals(
        primary_activity="legal_services",
        org_structure_state="absent",
        policy_state="verbal",
        risk_register_state="absent",
        internal_audit_state="absent",
        has_compliance_officer=False,
        has_board=False,
    )
    result = analyze(signals, _engine())
    for dim in MATURITY_DIMENSIONS:
        assert result.maturity_vision[dim]["score"] >= result.maturity[dim]["score"]
    # governance is driven by org_structure_state (currently 'absent') — the vision upgrades it
    assert result.maturity_vision["governance"]["score"] > result.maturity["governance"]["score"]


def test_governance_vision_does_not_alter_structural_facts() -> None:
    """Upgrading maturity for the vision must never change what sector/size an org is — only its
    process/policy-state signals move."""
    signals = make_signals(primary_activity="legal_services", employee_count=2)
    result = analyze(signals, _engine())
    # If sector/employee_count changed, active-pack composition would change too — it doesn't.
    assert result.capacity["tier"] == "micro"
