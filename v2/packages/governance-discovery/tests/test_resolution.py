"""Signal Resolution (ADR 0068) — the merge, proved rather than described.

Determinism, commutativity and idempotence are claimed structurally in `resolution.py` (a join on
a flat lattice). Claims about structure are exactly the kind that quietly stop being true, so each
one is exercised here against shuffled and repeated inputs rather than a single happy path.

Tests 1-6 and 13 of the ADR's table live here; the ones that need a database or the whole plan
pipeline live in the integration suites.
"""

from __future__ import annotations

import itertools
import random

import pytest
from governance_discovery.resolution import (
    ResolutionOutcome,
    SectorClaim,
    SignalOrigin,
    resolve,
)
from governance_discovery.signal import Signal, SignalSet, ValueType


def _core(**values) -> SignalSet:
    signals = SignalSet()
    for key, value in values.items():
        kind = ValueType.BOOLEAN if isinstance(value, bool) else ValueType.ENUM
        signals = signals.with_signal(Signal(key=key, value_type=kind, value=value))
    return signals


def _claim(key: str, value, *, release="rel_a", question=None, option="opt") -> SectorClaim:
    return SectorClaim(
        signal_key=key,
        value=value,
        release_id=release,
        question_id=question or f"q_{key}",
        option_id=option,
        value_type=ValueType.BOOLEAN if isinstance(value, bool) else ValueType.ENUM,
    )


# --- 1. ABSENT: the case the feature exists for -------------------------------------------------


def test_a_signal_the_interview_never_asked_is_filled_by_the_sector_answer() -> None:
    result = resolve(_core(handles_personal_data=True), [_claim("data_geography", "international")])

    assert result.signals.value("data_geography") == "international"
    record = result.resolved[0]
    assert record.outcome is ResolutionOutcome.ABSENT_FILLED
    assert record.origin is SignalOrigin.SECTOR_ANSWER
    assert record.core_claim is None
    assert not result.conflicts


def test_the_filled_signal_carries_full_confidence() -> None:
    """It is an ANSWER, not an inference: the customer said it, in a different room."""
    result = resolve(SignalSet(), [_claim("data_geography", "ksa_only")])
    assert result.signals.get("data_geography").confidence == 1.0


# --- 2. AGREE: corroboration, and the core interview stays the source ---------------------------


def test_agreement_changes_nothing_and_leaves_the_core_as_the_source() -> None:
    core = _core(data_geography="international")
    result = resolve(core, [_claim("data_geography", "international")])

    assert result.signals.as_dict() == core.as_dict()
    record = result.resolved[0]
    assert record.outcome is ResolutionOutcome.CORROBORATED
    assert record.origin is SignalOrigin.CORE_ANSWER, "agreement must not re-author the fact"
    assert record.core_claim is not None
    assert len(record.sector_claims) == 1, "the corroborating claim is still recorded"
    assert not result.conflicts


# --- 3. DISAGREE: no winner is invented ---------------------------------------------------------


def test_disagreement_leaves_the_core_value_standing_and_records_a_conflict() -> None:
    core = _core(data_geography="ksa_only")
    result = resolve(core, [_claim("data_geography", "international")])

    assert result.signals.value("data_geography") == "ksa_only"
    record = result.resolved[0]
    assert record.outcome is ResolutionOutcome.CONFLICT_CORE_STANDS
    assert record.origin is SignalOrigin.CORE_ANSWER
    assert result.conflicts == (record,)


# --- 4 & 5. Order independence and idempotence --------------------------------------------------


def test_the_merge_does_not_depend_on_the_order_of_the_claims() -> None:
    claims = [
        _claim("data_geography", "international", question="q1"),
        _claim("has_gov_clients", True, question="q2"),
        _claim("operates_critical_infrastructure", False, question="q3"),
        _claim("data_geography", "international", release="rel_b", question="q4"),
    ]
    core = _core(handles_personal_data=True)

    expected = resolve(core, claims)
    shuffled = random.Random(20260808)
    for _ in range(100):
        order = list(claims)
        shuffled.shuffle(order)
        outcome = resolve(core, order)
        assert outcome.signals.as_dict() == expected.signals.as_dict()
        assert outcome.as_audit() == expected.as_audit()


def test_every_permutation_of_a_conflicting_set_agrees() -> None:
    """Exhaustive rather than sampled, because a conflict is where an order-dependent
    implementation would actually show."""
    claims = [
        _claim("data_geography", "ksa_only", question="a"),
        _claim("data_geography", "international", question="b"),
        _claim("data_geography", "gcc", question="c"),
    ]
    results = {
        (r.signals.value("data_geography"), r.resolved[0].outcome)
        for r in (resolve(SignalSet(), list(p)) for p in itertools.permutations(claims))
    }
    assert results == {(None, ResolutionOutcome.CONFLICT_UNSET)}


def test_resolving_a_resolved_set_again_changes_nothing() -> None:
    claims = [_claim("data_geography", "international"), _claim("has_gov_clients", True)]
    once = resolve(_core(handles_personal_data=True), claims)
    twice = resolve(once.signals, claims)

    assert twice.signals.as_dict() == once.signals.as_dict()
    # Second time round the values are present, so the same claims now read as corroboration —
    # the SIGNALS are what must not move, and they do not.
    assert all(r.outcome is ResolutionOutcome.CORROBORATED for r in twice.resolved)


# --- 6. Two sector packs disagreeing, with the interview silent ---------------------------------


def test_two_packs_disagreeing_leave_the_signal_unset_rather_than_racing() -> None:
    result = resolve(
        SignalSet(),
        [
            _claim("data_geography", "ksa_only", release="rel_a"),
            _claim("data_geography", "international", release="rel_b"),
        ],
    )

    assert result.signals.has("data_geography") is False, "no decision rests on a fact in dispute"
    record = result.resolved[0]
    assert record.outcome is ResolutionOutcome.CONFLICT_UNSET
    assert record.origin is SignalOrigin.UNSET
    assert len(record.sector_claims) == 2


def test_two_packs_agreeing_fill_the_signal_once() -> None:
    result = resolve(
        SignalSet(),
        [
            _claim("has_gov_clients", True, release="rel_a"),
            _claim("has_gov_clients", True, release="rel_b"),
        ],
    )
    assert result.signals.value("has_gov_clients") is True
    assert result.resolved[0].outcome is ResolutionOutcome.ABSENT_FILLED


# --- 13. "We don't know" is not "no" ------------------------------------------------------------


@pytest.mark.parametrize("other", [None])
def test_a_null_claim_never_becomes_false(other) -> None:
    """The failure mode this contract exists to close: an unknown answer quietly deciding that an
    organization has no obligation."""
    result = resolve(SignalSet(), [_claim("has_gov_clients", other)])

    assert result.signals.has("has_gov_clients") is False
    assert result.signals.value("has_gov_clients") is not False
    assert result.resolved == (), "a claim with no value is not a claim, so there is nothing to log"


def test_a_null_claim_cannot_create_a_conflict_either() -> None:
    result = resolve(
        SignalSet(),
        [
            _claim("has_gov_clients", True, release="rel_a"),
            _claim("has_gov_clients", None, release="rel_b"),
        ],
    )
    assert result.signals.value("has_gov_clients") is True
    assert not result.conflicts


def test_a_null_claim_does_not_disturb_an_existing_core_answer() -> None:
    core = _core(has_gov_clients=False)
    result = resolve(core, [_claim("has_gov_clients", None)])
    assert result.signals.as_dict() == core.as_dict()
    assert result.resolved == ()


# --- signals nobody claimed ---------------------------------------------------------------------


def test_untouched_signals_are_carried_through_without_an_audit_record() -> None:
    """The record explains the sector channel; restating the whole interview in it would bury the
    part a reviewer needs to read."""
    core = _core(handles_personal_data=True, policy_state="approved")
    result = resolve(core, [_claim("has_gov_clients", True)])

    assert result.signals.value("policy_state") == "approved"
    assert [r.signal_key for r in result.resolved] == ["has_gov_clients"]
