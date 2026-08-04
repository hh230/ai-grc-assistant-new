"""The Rule Intent Verifier — does the proposed edit still MEAN what the rule meant?

The Minimal Fix Finder answers "does this work". It cannot answer "is this still the same rule",
and that gap is where its top-ranked candidate goes wrong:

    r:policy_weak_seeds_drafting
        policy_state lte verbal  →  policy_state lte reviewed_periodically
        benefit +3, regression 0

Statistically excellent. Semantically vandalism. The rule was named for organizations with **weak
policies**; the edit makes it fire for **everyone**, including organizations whose policies are
reviewed periodically. The defect count went down because the rule stopped discriminating — and a
rule that fires for everybody carries no information at all.

**Measured, not judged by a model.** Three deterministic signals, each of which a human would
recognise as the reason to reject the edit:

| signal | what it catches |
|---|---|
| **selectivity drift** | 18% of organizations → 91%: the threshold is now far too wide |
| **always fires** | a rule that never says "no" has stopped being a rule |
| **name incoherence** | `..._absent_...` whose predicate now accepts `approved` |

The output is a `SemanticDistance`, ranked alongside benefit, regression and blast radius — so a
candidate that scores well and means nothing sinks, instead of leading.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from devteam_harness.decisions import MATURITY_LADDER

# Above this share of the population, a rule has stopped discriminating. Not 100%: a rule firing
# for 96% of organizations is already carrying almost no information, and the point is to catch the
# edit BEFORE it becomes literally unconditional.
ALWAYS_FIRES_RATE = 0.95

# A rate change beyond this is a different rule wearing the same name.
SELECTIVITY_DRIFT_LIMIT = 0.35

# Tokens in a rule or seed id that ASSERT something about the predicate. A rule that calls itself
# `absent` and then accepts `approved` is misnamed, and a misnamed rule is how the next engineer
# gets it wrong.
NAME_ASSERTIONS: dict[str, frozenset[str]] = {
    # token in the id -> the ladder values the predicate may still accept
    "absent": frozenset({"absent"}),
    "weak": frozenset({"absent", "verbal"}),
    "unapproved": frozenset({"absent", "verbal", "documented_unapproved"}),
}


class SemanticDistance(enum.Enum):
    """How far an edit moved from what the rule was for."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def rank(self) -> int:
        return {"none": 0, "low": 1, "medium": 2, "high": 3}[self.value]


@dataclass
class IntentVerdict:
    """Why an edit is, or is not, still the rule it claims to be."""

    distance: SemanticDistance = SemanticDistance.NONE
    reasons: list[str] = field(default_factory=list)

    @property
    def preserved(self) -> bool:
        """Whether the edit is close enough to ship without a conversation about meaning."""
        return self.distance.rank <= SemanticDistance.LOW.rank

    def render(self) -> str:
        if not self.reasons:
            return "intent preserved"
        return f"{self.distance.value.upper()}: " + "; ".join(self.reasons)


def fire_rate(plans: dict[int, list[dict[str, Any]]], seed_id: str) -> float:
    """Share of organizations whose plan contains a given seeded task.

    A rule's observable footprint, measured from its OUTPUT rather than from engine internals — so
    this keeps working if rule evaluation is ever reimplemented.
    """
    if not plans:
        return 0.0
    firing = sum(
        1 for items in plans.values() if any(str(item["id"]) == seed_id for item in items)
    )
    return firing / len(plans)


def _ladder_span(op: str, value: str) -> frozenset[str]:
    """Which ladder values a predicate accepts. This is what "meaning" reduces to for a threshold."""
    if value not in MATURITY_LADDER:
        return frozenset()
    index = MATURITY_LADDER.index(value)
    spans = {
        "eq": {value},
        "lte": set(MATURITY_LADDER[: index + 1]),
        "lt": set(MATURITY_LADDER[:index]),
        "gte": set(MATURITY_LADDER[index:]),
        "gt": set(MATURITY_LADDER[index + 1 :]),
    }
    return frozenset(spans.get(op, set()))


def check_name_coherence(identifier: str, op: str, value: str) -> list[str]:
    """Does the predicate still match what the rule's own name asserts?

    `r:org_structure_absent_seeds_formalization` accepting `approved` is not a subtle problem: the
    name is the first thing the next engineer reads, and it would now be a lie.
    """
    accepted = _ladder_span(op, value)
    if not accepted:
        return []

    reasons = []
    lowered = identifier.lower()
    for token, allowed in NAME_ASSERTIONS.items():
        if token not in lowered:
            continue
        contradictions = accepted - allowed
        if contradictions:
            reasons.append(
                f"the name says '{token}' but the predicate now accepts "
                f"{sorted(contradictions)}"
            )
    return reasons


def verify_intent(
    *,
    identifier: str,
    op: str,
    value: str,
    rate_before: float,
    rate_after: float,
) -> IntentVerdict:
    """Judge one edit's faithfulness to the rule it changed."""
    verdict = IntentVerdict()
    worst = SemanticDistance.NONE

    def escalate(level: SemanticDistance) -> None:
        nonlocal worst
        if level.rank > worst.rank:
            worst = level

    # A rule that never says "no" has stopped being a rule.
    if rate_after >= ALWAYS_FIRES_RATE > rate_before:
        verdict.reasons.append(
            f"fires for {round(rate_after * 100)}% of organizations (was "
            f"{round(rate_before * 100)}%) — it no longer discriminates"
        )
        escalate(SemanticDistance.HIGH)

    drift = rate_after - rate_before
    if abs(drift) > SELECTIVITY_DRIFT_LIMIT:
        verdict.reasons.append(
            f"applies to {round(rate_before * 100)}% → {round(rate_after * 100)}% of "
            f"organizations"
        )
        escalate(SemanticDistance.HIGH if abs(drift) > 0.6 else SemanticDistance.MEDIUM)
    elif abs(drift) > SELECTIVITY_DRIFT_LIMIT / 2:
        escalate(SemanticDistance.LOW)

    for reason in check_name_coherence(identifier, op, value):
        verdict.reasons.append(reason)
        escalate(SemanticDistance.HIGH)

    verdict.distance = worst
    return verdict


@dataclass(frozen=True)
class EditSite:
    """Where an edit landed, and what the rule produces — enough to judge its intent.

    Parsed from the candidate rather than threaded through the search, so intent verification stays
    an independent check on the finder rather than something the finder asserts about itself.
    """

    identifier: str
    seed_id: str
    op: str
    value: str


def site_of(pack: dict[str, Any], rule_id: str) -> EditSite | None:
    """Find the rule a candidate targets, and the task it seeds."""
    for rule in pack.get("rules", []):
        if str(rule.get("id")) != rule_id:
            continue
        seed = (rule.get("effect") or {}).get("plan_seed") or {}
        predicate = rule.get("predicate") or {}
        return EditSite(
            identifier=f"{rule_id} {seed.get('id', '')}",
            seed_id=str(seed.get("id", "")),
            op=str(predicate.get("op", "")),
            value=str(predicate.get("value", "")),
        )
    return None


def parse_target(description: str) -> tuple[str, str] | None:
    """The `op value` a threshold candidate proposes, read from its own description.

    The description is the human-facing record of the edit; deriving the check from it means the
    verifier judges exactly what a reviewer would read, not a parallel representation that could
    drift from it.
    """
    if "→" not in description:
        return None
    after = description.split("→")[-1].strip().split()
    if len(after) < 3:
        return None
    return after[1], after[2]
