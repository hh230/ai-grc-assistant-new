"""Tests for the Rule Synthesizer and the SearchExhausted artifact.

The property that matters: synthesis is driven by EVIDENCE from the population, not by imagination,
and a synthesized rule must survive the same pipeline as a human's edit — including the Rule Intent
Verifier, which would reject a carelessly named one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from devteam_harness.investigation.intent import (
    IntentVerdict,
    SemanticDistance,
    check_name_coherence,
)
from devteam_harness.investigation.synthesis import (
    REMEDIATION,
    SearchExhausted,
    exhaustion_of,
    find_uncovered_states,
    propose,
    synthesize,
    with_rule,
)


@dataclass
class _Scenario:
    seed: int
    signals: dict[str, Any]


def _plan(signal: str | None) -> list[dict[str, Any]]:
    if signal is None:
        return []
    return [{"id": "seed:x", "resolves_signal": {"signal": signal, "value": "approved"}}]


# --- the artifact ---------------------------------------------------------------------------


@dataclass
class _Outcome:
    clean: bool
    regression: int = 0
    intent: IntentVerdict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.intent is None:
            self.intent = IntentVerdict()


def test_a_space_with_no_valid_fix_becomes_a_formal_artifact() -> None:
    """"We tried every threshold change and they all break the rule's meaning" is a DESIGN
    conclusion. If it lives only in a terminal, the same dead end gets proposed again."""
    outcomes = [
        _Outcome(clean=False, intent=IntentVerdict(distance=SemanticDistance.HIGH, reasons=["x"]))
        for _ in range(33)
    ]
    artifact = exhaustion_of(outcomes, space="thresholds", target="empty plans")

    assert artifact is not None
    assert artifact.status == "EXHAUSTED"
    assert artifact.candidates_tried == 33
    assert artifact.rejected_for == {"intent_high": 33}
    assert "NO VALID FIX EXISTS" in artifact.render()


def test_a_space_that_DOES_contain_a_fix_is_not_declared_exhausted() -> None:
    """Claiming a dead end that is not one is the reverse of a false positive, and just as bad:
    it would stop someone adopting a fix that works."""
    assert exhaustion_of([_Outcome(clean=True)], space="thresholds", target="x") is None


def test_the_artifact_records_WHY_each_candidate_was_rejected() -> None:
    """"33 failed" is not actionable. "33 failed on intent" points at the next move."""
    outcomes = [
        _Outcome(clean=False, regression=2),
        _Outcome(clean=False, intent=IntentVerdict(distance=SemanticDistance.HIGH, reasons=["x"])),
        _Outcome(clean=False),
    ]
    artifact = exhaustion_of(outcomes, space="thresholds", target="x")
    assert artifact is not None
    assert artifact.rejected_for == {"regression": 1, "intent_high": 1, "no_benefit": 1}


def test_an_unsearched_space_does_not_claim_exhaustion() -> None:
    assert SearchExhausted(space="s", target="t", candidates_tried=0).status == "NOT SEARCHED"


# --- evidence, not imagination ------------------------------------------------------------------


def test_an_uncovered_rung_is_found_from_the_POPULATION() -> None:
    """Organizations really sitting at `documented_unapproved` and receiving nothing, while
    `absent` organizations do receive something."""
    scenarios = [
        _Scenario(1, {"policy_state": "absent"}),
        _Scenario(2, {"policy_state": "documented_unapproved"}),
        _Scenario(3, {"policy_state": "documented_unapproved"}),
    ]
    plans = {1: _plan("policy_state"), 2: _plan(None), 3: _plan(None)}

    states = find_uncovered_states(scenarios, plans)
    assert len(states) == 1
    assert (states[0].signal, states[0].value) == ("policy_state", "documented_unapproved")
    assert states[0].organizations == 2
    assert states[0].covered_at == ("absent",)


def test_a_signal_no_rule_EVER_acts_on_is_not_a_synthesis_target() -> None:
    """That is a different defect — the Counterfactual Judge's `consequential_answer_ignored`.
    Conflating them would propose rules for questions the product deliberately does not act on."""
    scenarios = [_Scenario(1, {"policy_state": "absent"}), _Scenario(2, {"policy_state": "verbal"})]
    assert find_uncovered_states(scenarios, {1: _plan(None), 2: _plan(None)}) == []


def test_a_rung_that_is_already_covered_is_not_proposed_again() -> None:
    scenarios = [_Scenario(1, {"policy_state": "verbal"})]
    assert find_uncovered_states(scenarios, {1: _plan("policy_state")}) == []


def test_the_most_occupied_gap_is_proposed_first() -> None:
    """A rule for two organizations matters less than one for forty."""
    scenarios = [
        _Scenario(1, {"policy_state": "absent"}),
        *(_Scenario(n, {"policy_state": "verbal"}) for n in range(2, 6)),
        _Scenario(9, {"policy_state": "documented_unapproved"}),
    ]
    plans = {1: _plan("policy_state")}
    plans.update({n: _plan(None) for n in [*range(2, 6), 9]})

    states = find_uncovered_states(scenarios, plans)
    assert states[0].value == "verbal"
    assert states[0].organizations == 4


def test_a_signal_with_no_remediation_is_skipped() -> None:
    """The top rung needs nothing done to it — proposing a task there would be noise."""
    assert "reviewed_periodically" not in REMEDIATION


# --- the emitted rule ----------------------------------------------------------------------------


def _state(signal: str = "policy_state", value: str = "documented_unapproved") -> Any:
    scenarios = [_Scenario(1, {signal: "absent"}), _Scenario(2, {signal: value})]
    return find_uncovered_states(scenarios, {1: _plan(signal), 2: _plan(None)})[0]


def test_a_documented_but_unapproved_state_is_told_to_APPROVE_not_redraft() -> None:
    """Derived from the pack's own vocabulary: something already documented needs approving, not
    drafting again. Telling an organization to re-draft what it has written is the kind of advice
    that destroys trust in the whole plan."""
    rule = synthesize(_state())
    assert rule.seed_id == "seed:approve_policy"
    assert rule.rule["predicate"] == {
        "signal": "policy_state",
        "op": "eq",
        "value": "documented_unapproved",
    }
    assert rule.rule["effect"]["plan_seed"]["resolves_signal"]["value"] == "approved"


def test_a_synthesized_rule_is_named_so_the_INTENT_VERIFIER_accepts_it() -> None:
    """Naming is not cosmetic: a carelessly named rule would be rejected by the very pipeline meant
    to validate it — correctly. `..._unapproved_...` may accept `documented_unapproved`."""
    rule = synthesize(_state())
    predicate = rule.rule["predicate"]
    assert check_name_coherence(rule.rule_id, predicate["op"], predicate["value"]) == []


def test_a_synthesized_rule_carries_the_evidence_that_motivated_it() -> None:
    """A proposal without its reason cannot be reviewed, only accepted or refused on faith."""
    rule = synthesize(_state())
    assert "organization(s) with no task for it" in rule.describe()


def test_adding_a_rule_never_mutates_the_original_pack() -> None:
    """A new governance rule is the owner's decision. This proposes; it never adopts."""
    pack: dict[str, Any] = {"pack_id": "pack:x", "rules": [{"id": "r:existing"}]}
    extended = with_rule(pack, synthesize(_state()))

    assert len(pack["rules"]) == 1, "the original must be untouched"
    assert len(extended["rules"]) == 2


def test_propose_returns_one_rule_per_uncovered_state() -> None:
    scenarios = [
        _Scenario(1, {"policy_state": "absent"}),
        _Scenario(2, {"policy_state": "verbal"}),
        _Scenario(3, {"policy_state": "documented_unapproved"}),
    ]
    plans = {1: _plan("policy_state"), 2: _plan(None), 3: _plan(None)}
    proposals = propose(scenarios, plans)
    assert {rule.rule["predicate"]["value"] for rule in proposals} == {
        "verbal",
        "documented_unapproved",
    }


def test_every_proposal_uses_the_pack_s_own_rule_shape() -> None:
    """A rule the engine cannot parse is not a proposal, it is a crash waiting to happen."""
    rule = synthesize(_state()).rule
    assert set(rule) >= {"id", "version", "predicate", "effect"}
    seed = rule["effect"]["plan_seed"]
    assert set(seed) >= {"id", "pillar", "title_key", "rationale_key", "urgency", "effort_size"}
