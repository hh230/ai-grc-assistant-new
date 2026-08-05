"""Applicability derivation — sector implies obligations; rules key on the obligations.

The invariant that matters most here is the first one: an inference must never overwrite an
answer. Everything else is machinery.
"""

from __future__ import annotations

import pytest
from governance_discovery.analysis import analyze
from governance_discovery.derivation import (
    DERIVED_CONFIDENCE,
    MAX_DERIVATION_PASSES,
    Derivation,
    apply_derivations,
    derivations_from_packs,
    parse_derivation,
)
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.pack import load_bundled_packs
from governance_discovery.signal import Signal, SignalSet, ValueType

from tests.helpers import make_signals


def _engine() -> DiscoveryEngine:
    return DiscoveryEngine(load_bundled_packs())


def _signals(**values) -> SignalSet:
    types = {
        "primary_activity": ValueType.ENUM,
        "ownership_type": ValueType.ENUM,
        "data_geography": ValueType.ENUM,
        "handles_personal_data": ValueType.BOOLEAN,
        "has_gov_clients": ValueType.BOOLEAN,
        "is_government_linked": ValueType.BOOLEAN,
        "operates_critical_infrastructure": ValueType.BOOLEAN,
        "subject_to_nca": ValueType.BOOLEAN,
    }
    signals = SignalSet()
    for key, value in values.items():
        signals = signals.with_signal(Signal(key=key, value_type=types[key], value=value))
    return signals


def _bundled() -> tuple[Derivation, ...]:
    return derivations_from_packs(load_bundled_packs())


# --- the three invariants ------------------------------------------------------------------


def test_an_answer_always_beats_an_inference():
    """The customer knows their own operations; we only know what their sector usually implies.

    If they say they are not government-linked, a derivation from `has_gov_clients` must not
    silently overrule them.
    """
    answered = _signals(has_gov_clients=True, is_government_linked=False)
    outcome = apply_derivations(answered, _bundled())

    assert outcome.signals.value("is_government_linked") is False
    assert "d:gov_clients_is_government_linked" in outcome.overridden_by_answer
    assert not any(fact.signal_key == "is_government_linked" for fact in outcome.derived)


def test_an_overruled_derivation_is_recorded_not_discarded():
    """A systematic gap between what a sector implies and what customers report is information
    about the MODEL — invisible if we drop it."""
    outcome = apply_derivations(_signals(has_gov_clients=True, is_government_linked=False),
                                _bundled())
    assert outcome.overridden_by_answer


def test_every_derived_signal_carries_its_provenance_and_basis():
    outcome = apply_derivations(_signals(primary_activity="government"), _bundled())
    fact = next(f for f in outcome.derived if f.signal_key == "is_government_linked")

    assert fact.derivation_id == "d:government_sector_is_government_linked"
    assert fact.source_signals == ("primary_activity",)
    assert "NCA ECC" in fact.basis
    assert "primary_activity" in fact.explain()


def test_derivation_runs_to_a_fixpoint_not_a_single_pass():
    """`financial_services` → `provides_financial_services` → `subject_to_sama` is two links. A
    single pass would resolve only the first, and the SAMA rules would never fire."""
    outcome = apply_derivations(_signals(primary_activity="financial_services"), _bundled())
    derived = {fact.signal_key: fact.value for fact in outcome.derived}

    assert derived["provides_financial_services"] is True
    assert derived["subject_to_sama"] is True


def test_the_order_derivations_appear_in_a_pack_cannot_change_the_outcome():
    """Order-dependence in a data file is a trap for whoever edits it next."""
    forward = _bundled()
    outcome_a = apply_derivations(_signals(primary_activity="financial_services"), forward)
    outcome_b = apply_derivations(_signals(primary_activity="financial_services"),
                                  tuple(reversed(forward)))
    assert outcome_a.signals.as_dict() == outcome_b.signals.as_dict()


# --- safety --------------------------------------------------------------------------------


def test_a_chain_too_deep_to_settle_fails_loudly_rather_than_running_on():
    """What the pass bound actually guarantees.

    Termination itself is guaranteed by monotonicity — facts only ever accumulate, never change
    or disappear, so the loop cannot run forever. The bound is a *depth* limit, and it only bites
    under adverse ordering: a forward-ordered chain resolves entirely within a single pass,
    because each derivation sees what the previous one just wrote. Reversed, the same chain
    advances one link per pass, which is the worst case a knowledge pack can present.
    """
    chain = tuple(
        Derivation(id=f"d:{i}", when={"signal": f"s{i}", "op": "eq", "value": True},
                   derives_signal=f"s{i + 1}", derives_value=True,
                   value_type=ValueType.BOOLEAN, basis="test")
        for i in range(MAX_DERIVATION_PASSES + 2)
    )
    start = SignalSet().with_signal(Signal(key="s0", value_type=ValueType.BOOLEAN, value=True))

    assert apply_derivations(start, chain).signals.value(f"s{MAX_DERIVATION_PASSES + 2}") is True

    with pytest.raises(ValueError, match="did not settle"):
        apply_derivations(start, tuple(reversed(chain)))


def test_a_derivation_that_loops_back_onto_an_answer_settles():
    """`a → b → a` where `a` was answered: the return leg is refused by the answer-wins rule, so
    the loop closes instead of oscillating."""
    looping = (
        Derivation(id="d:a", when={"signal": "a", "op": "eq", "value": True},
                   derives_signal="b", derives_value=True, value_type=ValueType.BOOLEAN,
                   basis="test"),
        Derivation(id="d:b", when={"signal": "b", "op": "eq", "value": True},
                   derives_signal="a", derives_value=False, value_type=ValueType.BOOLEAN,
                   basis="test"),
    )
    start = SignalSet().with_signal(Signal(key="a", value_type=ValueType.BOOLEAN, value=True))
    outcome = apply_derivations(start, looping)

    assert outcome.signals.value("a") is True
    assert outcome.signals.value("b") is True
    assert "d:b" in outcome.overridden_by_answer


def test_two_derivations_deriving_the_same_signal_differently_is_a_contradiction():
    conflicting = (
        Derivation(id="d:yes", when={"signal": "a", "op": "eq", "value": True},
                   derives_signal="x", derives_value=True, value_type=ValueType.BOOLEAN,
                   basis="test"),
        Derivation(id="d:no", when={"signal": "a", "op": "eq", "value": True},
                   derives_signal="x", derives_value=False, value_type=ValueType.BOOLEAN,
                   basis="test"),
    )
    start = SignalSet().with_signal(Signal(key="a", value_type=ValueType.BOOLEAN, value=True))
    with pytest.raises(ValueError, match="contradictory"):
        apply_derivations(start, conflicting)


def test_several_derivations_agreeing_on_a_value_is_not_a_conflict():
    """Government sector AND government clients both imply the same thing. That is convergence,
    not contradiction — three routes to one conclusion is how applicability actually works."""
    outcome = apply_derivations(
        _signals(primary_activity="government", has_gov_clients=True,
                 ownership_type="government_owned"),
        _bundled(),
    )
    assert outcome.signals.value("is_government_linked") is True
    assert outcome.signals.value("subject_to_nca") is True


def test_a_derivation_must_cite_a_regulatory_basis():
    with pytest.raises(ValueError, match="regulatory basis"):
        parse_derivation({"id": "d:x", "when": {}, "derives_signal": "y", "derives_value": True,
                          "value_type": "boolean", "basis": "  "})


def test_a_derivation_id_must_be_namespaced():
    with pytest.raises(ValueError, match="must start with 'd:'"):
        parse_derivation({"id": "x", "when": {}, "derives_signal": "y", "derives_value": True,
                          "value_type": "boolean", "basis": "b"})


def test_derived_signals_are_stamped_below_full_confidence():
    """An inference is weaker evidence than an answer, and a plan resting on one should say so."""
    outcome = apply_derivations(_signals(primary_activity="government"), _bundled())
    assert outcome.signals.get("subject_to_nca").confidence == DERIVED_CONFIDENCE
    assert DERIVED_CONFIDENCE < 1.0


# --- the point of the whole exercise ---------------------------------------------------------


def test_sector_now_changes_the_plan_through_derived_obligations():
    """Government and financial services no longer receive the identical plan a marketing agency
    gets — and they get it via `subject_to_nca` / `subject_to_sama`, not a sector-keyed rule."""
    def plan_for(sector: str) -> set[str]:
        signals = make_signals(
            primary_activity=sector, employee_count=120, provides_saas=False,
            has_compliance_officer=False, has_board=False, org_structure_state="absent",
            policy_state="absent", risk_register_state="absent", internal_audit_state="absent",
            has_legal_team=False, has_it_team=False, execution_capacity="allocated_time",
            handles_personal_data=False, has_gov_clients=False, ownership_type="private",
            outsources_critical_functions=False,
        )
        return {item["id"] for item in analyze(signals, _engine()).plan_items}

    generic = plan_for("marketing_advertising")
    assert plan_for("government") != generic
    assert plan_for("financial_services") != generic
    assert "seed:align_with_sama_csf" in plan_for("financial_services")
    assert "seed:confirm_regulatory_applicability" in plan_for("government")


def test_no_derived_signal_collides_with_a_signal_a_QUESTION_writes():
    """`analyze` resolves derivations before computing coverage, which is only safe while these
    two namespaces stay disjoint. If a future pack ever derives a signal a question also writes,
    an inference would silently count as an answer and inflate confidence — so the separation is
    guarded here rather than assumed."""
    packs = load_bundled_packs()
    written = {q.writes_signal for pack in packs.values() for q in pack.questions}
    derived = {d.derives_signal for d in derivations_from_packs(packs)}

    assert derived, "no derivations loaded — this test would pass vacuously"
    collision = sorted(written & derived)
    assert not collision, f"question and derivation both write: {collision}"


def test_derived_obligations_never_count_as_answered_questions():
    """Confidence must rest on what the customer told us, never on our own inferences —
    otherwise the engine grows more confident the more it guesses."""
    engine = _engine()
    signals = make_signals(
        primary_activity="government", employee_count=50, provides_saas=False,
        has_compliance_officer=True, has_board=True, org_structure_state="approved",
        policy_state="approved", risk_register_state="approved", internal_audit_state="approved",
        has_legal_team=False, has_it_team=False, execution_capacity="allocated_time",
        handles_personal_data=False, has_gov_clients=False,
    )
    answered, total = engine.required_question_coverage(signals)
    # `subject_to_nca` and `is_government_linked` are in the resolved set but are not questions,
    # so they can neither inflate `answered` nor appear in `total`.
    assert answered < total
    assert engine.resolve(signals).value("subject_to_nca") is True
