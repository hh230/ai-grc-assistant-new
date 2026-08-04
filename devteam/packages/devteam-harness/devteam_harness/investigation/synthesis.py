"""The Rule Synthesizer — when no EDIT can fix it, propose a new RULE.

The Minimal Fix Finder searches the space of edits to existing rules. On the empty-plan defect it
searched that space exhaustively and every candidate destroyed the rule's meaning — all 33 scored
HIGH semantic distance, zero clean. That is not a failure of the search; it is a **result**:

    the fix does not exist in this space

`SearchExhausted` below makes that a first-class artifact rather than an observation someone made
once in a terminal. It is a design fact — "we proved no threshold change works" — and design facts
must outlive the run that produced them, or the next person re-proposes the same dead end.

**Bounded program synthesis, not AI.** The reason no edit works is specific and diagnosable: the
ruleset has no concept for the state those organizations are actually in. Every rule fires on
`absent`; nobody covers `documented_unapproved`. So the synthesizer does not invent freely — it
finds **uncovered states from the population** and emits the one rule shape the pack already uses:

    WHEN  <signal> == <uncovered value>
    THEN  emit seed: <remediation for that state>

A synthesized rule is then verified by exactly the same pipeline as a human's edit — counterfactual,
decision rules, intent, regression, diff. If it survives, it is proposed. If not, it is discarded.
Nothing is adopted: a new governance rule is the owner's decision.

The LLM's job comes after this and is correspondingly small: given three synthesized rules that all
already work, say which is closest to the spirit of the framework, or which duplicates an existing
rule. It never invents one from nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from devteam_harness.decisions import MATURITY_LADDER

# What a state needs done to it, and where that lands the organization. Derived from the pack's own
# vocabulary: existing seeds `draft`, `establish` and `formalize` all target `approved`, so a state
# that is already documented needs approving rather than re-drafting.
REMEDIATION: dict[str, tuple[str, str]] = {
    "absent": ("establish", "approved"),
    "verbal": ("formalize", "approved"),
    "documented_unapproved": ("approve", "approved"),
    "approved": ("schedule_review", "reviewed_periodically"),
}

# Signals whose values move along the maturity ladder — the only ones a state-coverage argument
# applies to. A boolean has no "uncovered rung".
LADDER_SIGNALS: frozenset[str] = frozenset(
    {"policy_state", "org_structure_state", "risk_register_state", "internal_audit_state"}
)


@dataclass(frozen=True)
class SearchExhausted:
    """A formal record that a search space contains no valid fix.

    Deliberately an artifact, not a log line. "We tried every threshold change and they all break
    the rule's meaning" is a design conclusion that should be citable months later — otherwise the
    same dead end gets proposed again, and the work of ruling it out is spent twice.
    """

    space: str
    target: str
    candidates_tried: int
    rejected_for: dict[str, int] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "EXHAUSTED" if self.candidates_tried else "NOT SEARCHED"

    def render(self) -> str:
        reasons = "  ".join(f"{reason}={count}" for reason, count in sorted(self.rejected_for.items()))
        return "\n".join(
            [
                "Decision Search",
                f"  status       : {self.status}",
                f"  search space : {self.space}",
                f"  target       : {self.target}",
                f"  tried        : {self.candidates_tried} candidate(s)",
                f"  rejected for : {reasons or 'n/a'}",
                "  result       : NO VALID FIX EXISTS IN THIS SPACE",
            ]
        )


def exhaustion_of(outcomes: list[Any], *, space: str, target: str) -> SearchExhausted | None:
    """Turn a search that found nothing usable into the artifact that says so.

    Returns None when a clean candidate exists — there is nothing to declare exhausted, and
    claiming otherwise would be the reverse of a false positive: a false dead end.
    """
    if any(outcome.clean for outcome in outcomes):
        return None

    rejected: dict[str, int] = {}
    for outcome in outcomes:
        if outcome.regression:
            reason = "regression"
        elif not outcome.intent.preserved:
            reason = f"intent_{outcome.intent.distance.value}"
        else:
            reason = "no_benefit"
        rejected[reason] = rejected.get(reason, 0) + 1

    return SearchExhausted(
        space=space, target=target, candidates_tried=len(outcomes), rejected_for=rejected
    )


# --- finding what the ruleset cannot see --------------------------------------------------------


@dataclass(frozen=True)
class UncoveredState:
    """A signal value that organizations really hold and no rule acts on.

    Evidence-based, not imagined: `organizations` counts real scenarios sitting in this state whose
    plan contains nothing addressing that signal. A state nobody occupies is not worth a rule.
    """

    signal: str
    value: str
    organizations: int
    covered_at: tuple[str, ...]

    def describe(self) -> str:
        return (
            f"{self.signal} == {self.value}: {self.organizations} organization(s) with no task "
            f"for it (the ruleset covers {list(self.covered_at)})"
        )


def find_uncovered_states(
    scenarios: list[Any], plans: dict[int, list[dict[str, Any]]]
) -> list[UncoveredState]:
    """Ladder rungs where organizations sit and receive nothing.

    A rung is uncovered when organizations hold that value and none of them gets a task resolving
    that signal, WHILE some other rung does get one. The second half matters: a signal no rule ever
    acts on is a different problem (the Counterfactual Judge's `consequential_answer_ignored`), and
    conflating them would propose rules for questions the product deliberately does not act on.
    """
    occupancy: dict[tuple[str, str], list[int]] = {}
    covered: dict[str, set[str]] = {}

    for scenario in scenarios:
        items = plans.get(scenario.seed, [])
        resolved = {
            str((item.get("resolves_signal") or {}).get("signal"))
            for item in items
        }
        for signal, value in scenario.signals.items():
            if signal not in LADDER_SIGNALS or value not in MATURITY_LADDER:
                continue
            if signal in resolved:
                covered.setdefault(signal, set()).add(str(value))
            else:
                occupancy.setdefault((signal, str(value)), []).append(scenario.seed)

    uncovered = []
    for (signal, value), seeds in sorted(occupancy.items()):
        covered_values = covered.get(signal, set())
        if not covered_values or value in covered_values:
            continue  # either the signal is acted on nowhere, or this rung already is
        if value not in REMEDIATION:
            continue  # the top rung needs nothing done to it
        uncovered.append(
            UncoveredState(
                signal=signal,
                value=value,
                organizations=len(seeds),
                covered_at=tuple(sorted(covered_values)),
            )
        )
    return sorted(uncovered, key=lambda state: -state.organizations)


# --- emitting a rule the pack would accept --------------------------------------------------------


def _root(signal: str) -> str:
    """`policy_state` -> `policy`. The noun the rule and its seed are named for."""
    return signal.removesuffix("_state")


@dataclass(frozen=True)
class SynthesizedRule:
    """A proposed rule, plus the evidence that motivated it."""

    rule: dict[str, Any]
    motivation: UncoveredState

    @property
    def rule_id(self) -> str:
        return str(self.rule["id"])

    @property
    def seed_id(self) -> str:
        return str(self.rule["effect"]["plan_seed"]["id"])

    def describe(self) -> str:
        predicate = self.rule["predicate"]
        return (
            f"{self.rule_id}\n"
            f"    WHEN  {predicate['signal']} {predicate['op']} {predicate['value']}\n"
            f"    THEN  emit {self.seed_id}\n"
            f"    because {self.motivation.describe()}"
        )


def synthesize(state: UncoveredState) -> SynthesizedRule:
    """Emit the one rule shape this pack uses, named so it means what it does.

    Naming is not cosmetic here: the Rule Intent Verifier checks that a rule's name does not
    contradict its predicate, so a synthesized rule that is carelessly named would be rejected by
    the very pipeline meant to validate it — correctly.
    """
    verb, target = REMEDIATION[state.value]
    root = _root(state.signal)
    seed_id = f"seed:{verb}_{root}"
    rule_id = f"r:{root}_{state.value}_seeds_{verb}"

    return SynthesizedRule(
        rule={
            "id": rule_id,
            "version": "1.0",
            "predicate": {"signal": state.signal, "op": "eq", "value": state.value},
            "effect": {
                "plan_seed": {
                    "id": seed_id,
                    "pillar": "policies" if root == "policy" else "organization",
                    "title_key": f"plan.seed.{verb}_{root}.title",
                    "rationale_key": f"plan.seed.{verb}_{root}.rationale",
                    "urgency": "high",
                    "effort_size": "medium",
                    "resolves_signal": {"signal": state.signal, "value": target},
                }
            },
        },
        motivation=state,
    )


def propose(
    scenarios: list[Any], plans: dict[int, list[dict[str, Any]]]
) -> list[SynthesizedRule]:
    """Every rule the population says is missing, most-needed first."""
    return [synthesize(state) for state in find_uncovered_states(scenarios, plans)]


def with_rule(pack: dict[str, Any], synthesized: SynthesizedRule) -> dict[str, Any]:
    """A copy of the pack with the proposed rule added. The original is never touched."""
    import copy

    candidate = copy.deepcopy(pack)
    candidate.setdefault("rules", []).append(copy.deepcopy(synthesized.rule))
    return candidate
