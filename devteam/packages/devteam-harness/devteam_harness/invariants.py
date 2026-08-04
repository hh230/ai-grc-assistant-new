"""Invariants — properties that must hold for EVERY concluded scenario.

An invariant is not a unit test of one example; it is a claim about all possible organizations,
checked against thousands of them. Each returns violations rather than asserting, so one bad
scenario is recorded and the run continues.

Every invariant here was probed against a real population before being encoded — asserting
something the system never actually guaranteed would make the harness lie. One of them
(`plan_dependencies_exist`) genuinely fails today and is documented as a real product finding
rather than quietly weakened to green.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MATURITY_DIMENSIONS = frozenset({"governance", "risk", "compliance", "cyber", "leadership"})
VALID_PRIORITIES = frozenset({"critical", "high", "medium", "low"})
VALID_EFFORT_SIZES = frozenset({"small", "medium", "large"})
VALID_TIMEFRAMES = frozenset({"week_1", "week_2", "month_1", "month_3", "month_6", "year_1"})
VALID_CONFIDENCE = frozenset({"normal", "low"})


@dataclass(frozen=True)
class Violation:
    """One broken invariant on one scenario. `name` groups; `detail` reproduces."""

    name: str
    detail: str


def _maturity_covers_all_dimensions(applicability: Any) -> list[Violation]:
    actual = set(applicability.maturity)
    if actual != set(MATURITY_DIMENSIONS):
        return [
            Violation(
                "maturity_covers_all_dimensions",
                f"expected {sorted(MATURITY_DIMENSIONS)}, got {sorted(actual)}",
            )
        ]
    return []


def _stars_within_scale(applicability: Any) -> list[Violation]:
    out = []
    for dimension, rating in applicability.maturity.items():
        stars = rating.get("stars")
        if not isinstance(stars, int) or not 0 <= stars <= 5:
            out.append(Violation("stars_within_scale", f"{dimension} stars={stars!r}"))
    return out


def _vision_never_below_baseline(applicability: Any) -> list[Violation]:
    """Executing a plan may never make an organization *less* mature. A vision below its own
    baseline would mean the product is advising work that regresses the client."""
    out = []
    for dimension, baseline in applicability.maturity.items():
        vision = applicability.maturity_vision.get(dimension)
        if vision is None:
            out.append(Violation("vision_never_below_baseline", f"{dimension} missing in vision"))
        elif vision["score"] < baseline["score"]:
            out.append(
                Violation(
                    "vision_never_below_baseline",
                    f"{dimension}: vision {vision['score']} < baseline {baseline['score']}",
                )
            )
    return out


def _confidence_well_formed(applicability: Any) -> list[Violation]:
    out = []
    score = applicability.confidence_score
    if not isinstance(score, (int, float)) or not 0.0 <= float(score) <= 1.0:
        out.append(Violation("confidence_well_formed", f"score={score!r}"))
    if applicability.confidence not in VALID_CONFIDENCE:
        out.append(Violation("confidence_well_formed", f"label={applicability.confidence!r}"))
    return out


def _plan_item_ids_unique(applicability: Any) -> list[Violation]:
    ids = [item["id"] for item in applicability.plan_items]
    duplicates = {i for i in ids if ids.count(i) > 1}
    return [Violation("plan_item_ids_unique", f"duplicates={sorted(duplicates)}")] if duplicates else []


def _plan_dependencies_exist(applicability: Any) -> list[Violation]:
    """Every `depends_on_item_ids` entry must name an item that is actually in the plan.

    FOUND AND FIXED — this is the first real product defect the harness caught. Plan seeds are
    emitted by independent rules in `packs/core.json`, and a seed may declare a dependency on a
    seed whose own rule did not fire: `r:policy_weak_seeds_drafting` (predicate
    `policy_state <= verbal`) emits `seed:draft_foundational_policies`, which declares
    `depends_on: ["seed:formalize_org_structure"]` — but that item is only emitted by
    `r:org_structure_absent_seeds_formalization` (predicate `org_structure_state == absent`).
    It failed on ~15% of generated organizations.

    The root cause was in `governance_discovery/scheduler.py::_as_item`, which copied
    `depends_on` verbatim into the persisted item even though the ordering pass had already
    established those ids were not in the plan. Fixed there; this invariant now guards the fix.
    """
    known = {item["id"] for item in applicability.plan_items}
    out = []
    for item in applicability.plan_items:
        for dependency in item.get("depends_on_item_ids") or ():
            if dependency not in known:
                out.append(
                    Violation(
                        "plan_dependencies_exist",
                        f"{item['id']} depends on missing {dependency}",
                    )
                )
    return out


def _plan_item_enums_valid(applicability: Any) -> list[Violation]:
    out = []
    for item in applicability.plan_items:
        for field, allowed in (
            ("priority", VALID_PRIORITIES),
            ("effort_size", VALID_EFFORT_SIZES),
            ("timeframe_bucket", VALID_TIMEFRAMES),
        ):
            value = item.get(field)
            if value not in allowed:
                out.append(Violation("plan_item_enums_valid", f"{item['id']}.{field}={value!r}"))
    return out


def _framework_confidence_in_range(applicability: Any) -> list[Violation]:
    out = []
    for framework in applicability.frameworks:
        confidence = framework.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
            out.append(
                Violation(
                    "framework_confidence_in_range",
                    f"{framework.get('framework_id')}={confidence!r}",
                )
            )
    return out


def check_applicability(applicability: Any) -> list[Violation]:
    """Every invariant that reads only the concluded analysis."""
    violations: list[Violation] = []
    for check in (
        _maturity_covers_all_dimensions,
        _stars_within_scale,
        _vision_never_below_baseline,
        _confidence_well_formed,
        _plan_item_ids_unique,
        _plan_dependencies_exist,
        _plan_item_enums_valid,
        _framework_confidence_in_range,
    ):
        violations.extend(check(applicability))
    return violations


def check_transcript(turns: list[Any]) -> list[Violation]:
    """Invariants about how the interview was conducted."""
    violations: list[Violation] = []

    asked = [turn.question_id for turn in turns]
    repeated = {q for q in asked if asked.count(q) > 1}
    if repeated:
        violations.append(Violation("no_question_asked_twice", f"repeated={sorted(repeated)}"))

    for turn in turns:
        if turn.skipped and turn.required:
            violations.append(
                Violation("required_questions_never_skipped", f"skipped {turn.question_id}")
            )
    return violations
