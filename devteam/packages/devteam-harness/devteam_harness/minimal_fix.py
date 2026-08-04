"""The Minimal Fix Finder — not "here is a problem", but "here is the smallest change that fixes it".

This is the step that was still human. The Counterfactual Judge and the Decision Verifier both end
at "something is wrong"; deciding *what to change* was left to a person reading rule files. This
closes that loop:

    found a defect → generate candidate changes → replay the population →
    did the defect go? → what regressed? → rank

**A search engine, not an AI.** The space of edits a product owner may make is small, enumerable
and typed, so searching it exhaustively is both cheaper and more trustworthy than asking a model to
invent one: every candidate here is a real edit, already applied and already measured. An LLM's
proper job comes later — ranking five changes that are all known to work — which is a far smaller
question than "choose the fix", and a far smaller surface for being wrong.

**The search space is exactly what a product owner owns**: thresholds, predicates, priorities, and
dependencies. Nothing generates code, and nothing touches the engine — only the knowledge pack's
data. That boundary is the safety property: a candidate can be reviewed as a JSON diff, and the
worst a bad one can do is be rejected.

**Nothing is written.** Candidates are applied to an in-memory copy of the pack via
`pack_from_dict`; `core.json` is never modified. Changing a governance rule is the owner's decision
(see the standing ruling on product rules), so this proposes and measures — it never adopts.
"""

from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from typing import Any

from devteam_harness.decisions import MATURITY_LADDER, PlanContext, verify_decision

# Comparison operators the pack's predicates use. A candidate may only ever move a predicate to
# another operator the engine already understands.
COMPARISON_OPS: tuple[str, ...] = ("eq", "lte", "lt", "gte", "gt")

# A flat penalty for having ANY regression, on top of the per-defect one — see `Outcome.score`.
REGRESSION_CATEGORY_PENALTY = 5

# Priorities a plan seed may carry, worst-first.
PRIORITIES: tuple[str, ...] = ("critical", "high", "medium", "low")


@dataclass(frozen=True)
class Candidate:
    """One proposed edit, described in the vocabulary of the file a human would edit."""

    space: str  # threshold | predicate | priority | dependency
    rule_id: str
    description: str
    mutate: Any  # (pack_dict) -> None, applied to a deep copy

    def __str__(self) -> str:
        return f"[{self.space}] {self.rule_id}: {self.description}"


@dataclass
class Outcome:
    """What a candidate actually did to the population — benefit and cost, never just benefit."""

    candidate: Candidate
    fixed: dict[str, int] = field(default_factory=dict)
    introduced: dict[str, int] = field(default_factory=dict)
    plans_changed: int = 0

    @property
    def benefit(self) -> int:
        return sum(self.fixed.values())

    @property
    def regression(self) -> int:
        return sum(self.introduced.values())

    @property
    def score(self) -> float:
        """Benefit, penalised hard by regression and gently by blast radius.

        A change that fixes six defects and introduces one is NOT a net win of five: a regression
        is a new defect shipped to organizations that were previously fine, which is worse than
        leaving a known one in place. The multiplier encodes that asymmetry rather than pretending
        the two are commensurate.

        Zero regression is a CATEGORY, not a point on a scale, so any regression at all takes a
        flat penalty on top of the per-defect one. Without it the arithmetic works out so that
        "fix 6, break 1" ties with "fix 3 cleanly", and a candidate that ships a new defect would
        rank alongside one that ships none.

        Blast radius breaks ties: between two changes that fix the same defects with no regression,
        the one that disturbs fewer plans is the safer edit.
        """
        penalty = (self.regression * 3) + (REGRESSION_CATEGORY_PENALTY if self.regression else 0)
        return self.benefit - penalty - (self.plans_changed * 0.01)

    @property
    def clean(self) -> bool:
        return self.benefit > 0 and self.regression == 0

    def render(self) -> str:
        lines = [
            str(self.candidate),
            f"    benefit    : +{self.benefit}  {self.fixed or ''}",
            f"    regression : {self.regression}  {self.introduced or ''}",
            f"    blast      : {self.plans_changed} plan(s) changed",
            f"    score      : {round(self.score, 2)}",
        ]
        return "\n".join(lines)


# --- candidate generation: only what a product owner may change ---------------------------------


def _predicate_sites(
    node: Any, path: tuple[Any, ...] = ()
) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
    """Every leaf predicate inside a rule, with the path needed to rewrite it in place.

    Predicates nest through `all`/`any`, so a flat scan would miss the composite rules — which are
    exactly the ones expressing the most interesting conditions.
    """
    sites: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    if isinstance(node, dict):
        if "signal" in node and "op" in node:
            sites.append((path, node))
        for key in ("all", "any"):
            for index, child in enumerate(node.get(key, ())):
                sites.extend(_predicate_sites(child, (*path, key, index)))
    return sites


def _set_at(root: dict[str, Any], path: tuple[Any, ...], **fields: Any) -> None:
    node: Any = root
    for step in path:
        node = node[step]
    node.update(fields)


def threshold_candidates(pack: dict[str, Any]) -> list[Candidate]:
    """Move a predicate's operator or value along the maturity ladder.

    This is the space the live findings sit in: `policy_state <= verbal` never fires for an
    organization at `documented_unapproved`, which is how six organizations receive an empty plan.
    """
    candidates: list[Candidate] = []
    for rule_index, rule in enumerate(pack.get("rules", [])):
        for path, predicate in _predicate_sites(rule.get("predicate", {})):
            if predicate.get("value") not in MATURITY_LADDER:
                continue
            signal = predicate["signal"]
            for op, value in itertools.product(COMPARISON_OPS, MATURITY_LADDER):
                if op == predicate["op"] and value == predicate["value"]:
                    continue

                def mutate(
                    doc: dict[str, Any],
                    _index: int = rule_index,
                    _path: tuple[Any, ...] = path,
                    _op: str = op,
                    _value: str = value,
                ) -> None:
                    _set_at(doc["rules"][_index]["predicate"], _path, op=_op, value=_value)

                candidates.append(
                    Candidate(
                        space="threshold",
                        rule_id=str(rule.get("id", rule_index)),
                        description=(
                            f"{signal} {predicate['op']} {predicate['value']}"
                            f"  →  {signal} {op} {value}"
                        ),
                        mutate=mutate,
                    )
                )
    return candidates


def priority_candidates(pack: dict[str, Any]) -> list[Candidate]:
    """Raise or lower a seeded task's urgency."""
    candidates: list[Candidate] = []
    for rule_index, rule in enumerate(pack.get("rules", [])):
        seed = (rule.get("effect") or {}).get("plan_seed")
        if not seed:
            continue
        current = seed.get("urgency")
        for urgency in PRIORITIES:
            if urgency == current:
                continue

            def mutate(
                doc: dict[str, Any], _index: int = rule_index, _urgency: str = urgency
            ) -> None:
                doc["rules"][_index]["effect"]["plan_seed"]["urgency"] = _urgency

            candidates.append(
                Candidate(
                    space="priority",
                    rule_id=str(rule.get("id", rule_index)),
                    description=f"{seed.get('id')} urgency {current} → {urgency}",
                    mutate=mutate,
                )
            )
    return candidates


def dependency_candidates(pack: dict[str, Any]) -> list[Candidate]:
    """Remove a declared dependency.

    Only removal is generated. Adding one requires knowing which prerequisite is meant, which is a
    judgement about the domain — precisely the thing a search must not guess at.
    """
    candidates: list[Candidate] = []
    for rule_index, rule in enumerate(pack.get("rules", [])):
        seed = (rule.get("effect") or {}).get("plan_seed") or {}
        for dependency in seed.get("depends_on", ()):

            def mutate(
                doc: dict[str, Any], _index: int = rule_index, _dependency: str = dependency
            ) -> None:
                node = doc["rules"][_index]["effect"]["plan_seed"]
                node["depends_on"] = [d for d in node.get("depends_on", []) if d != _dependency]

            candidates.append(
                Candidate(
                    space="dependency",
                    rule_id=str(rule.get("id", rule_index)),
                    description=f"{seed.get('id')} drop dependency on {dependency}",
                    mutate=mutate,
                )
            )
    return candidates


def generate_candidates(pack: dict[str, Any]) -> list[Candidate]:
    return [
        *threshold_candidates(pack),
        *priority_candidates(pack),
        *dependency_candidates(pack),
    ]


# --- evaluation ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """One organization's answers, captured once and replayed against every candidate.

    Signals are held CONSTANT rather than re-running the interview: the whole point is to measure
    what the rule change did, and an adaptive interview would change which questions were asked,
    mixing the edit's effect with interview drift.
    """

    seed: int
    signals: dict[str, Any]
    value_types: dict[str, str]


def findings_for(applicability: Any, scenario: Scenario) -> list[str]:
    """The decision-rule findings one plan produces, as rule names."""
    context = PlanContext(
        signals=dict(scenario.signals),
        plan_items=list(applicability.plan_items),
        gaps=list(applicability.gaps or ()),
        maturity=dict(applicability.maturity or {}),
        capacity=dict(applicability.capacity or {}),
    )
    return [finding.rule for finding in verify_decision(context)]


def _tally(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


@dataclass(frozen=True)
class Baseline:
    """The unmodified population: what each organization is told today, and what is wrong with it.

    Captured once and passed explicitly rather than held in module state — a search is a pure
    function of (scenarios, pack), and hidden state would make two concurrent searches silently
    contaminate each other.
    """

    findings: dict[int, list[str]]
    plans: dict[int, list[dict[str, Any]]]


def evaluate(
    candidate: Candidate,
    scenarios: list[Scenario],
    pack: dict[str, Any],
    baseline: Baseline,
    *,
    analyse: Any,
) -> Outcome:
    """Apply one candidate to a COPY of the pack and replay the whole population against it."""
    from devteam_harness.diff import diff_plans

    mutated = copy.deepcopy(pack)
    candidate.mutate(mutated)
    outcome = Outcome(candidate=candidate)

    fixed: list[str] = []
    introduced: list[str] = []

    for scenario in scenarios:
        try:
            applicability = analyse(mutated, scenario)
        except Exception:  # noqa: BLE001 — a candidate that breaks the engine scores badly
            introduced.append("candidate_crashed_the_engine")
            continue

        after = findings_for(applicability, scenario)
        before = baseline.findings.get(scenario.seed, [])

        before_counts, after_counts = _tally(before), _tally(after)
        for rule in set(before_counts) | set(after_counts):
            delta = after_counts.get(rule, 0) - before_counts.get(rule, 0)
            if delta < 0:
                fixed.extend([rule] * -delta)
            elif delta > 0:
                introduced.extend([rule] * delta)

        if diff_plans(
            list(baseline.plans.get(scenario.seed, [])), list(applicability.plan_items)
        ).magnitude:
            outcome.plans_changed += 1

    outcome.fixed = _tally(fixed)
    outcome.introduced = _tally(introduced)
    return outcome


def search(
    scenarios: list[Scenario],
    pack: dict[str, Any],
    *,
    analyse: Any,
    target_rule: str | None = None,
    limit: int | None = None,
) -> list[Outcome]:
    """Search the edit space and rank what actually helps.

    `target_rule` narrows the search to candidates that fix a specific finding — the usual way this
    is used, since the question is normally "what fixes THIS" rather than "what could be better".
    """
    findings: dict[int, list[str]] = {}
    plans: dict[int, list[dict[str, Any]]] = {}
    for scenario in scenarios:
        applicability = analyse(pack, scenario)
        findings[scenario.seed] = findings_for(applicability, scenario)
        plans[scenario.seed] = list(applicability.plan_items)
    baseline = Baseline(findings=findings, plans=plans)

    candidates = generate_candidates(pack)
    if limit is not None:
        candidates = candidates[:limit]

    outcomes = [
        evaluate(candidate, scenarios, pack, baseline, analyse=analyse) for candidate in candidates
    ]

    if target_rule is not None:
        outcomes = [outcome for outcome in outcomes if outcome.fixed.get(target_rule)]

    # Best first: highest score, then smallest blast radius among equals.
    return sorted(outcomes, key=lambda o: (-o.score, o.plans_changed))


def render_ranking(outcomes: list[Outcome], *, top: int = 5) -> str:
    if not outcomes:
        return "no candidate improved anything"
    lines = [f"{len(outcomes)} candidate(s) improved something; top {min(top, len(outcomes))}:"]
    lines.extend(outcome.render() for outcome in outcomes[:top])
    return "\n".join(lines)
