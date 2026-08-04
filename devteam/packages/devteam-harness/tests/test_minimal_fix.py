"""Tests for the Minimal Fix Finder and the Decision Diff.

The engine is injected, so these run without the real pack: what is pinned is the search space
(only what a product owner may change), the scoring asymmetry (a regression is not cancelled by a
fix), and the guarantee that nothing on disk is touched.
"""

from __future__ import annotations

import copy
import json
import pathlib
from typing import Any

from devteam_harness.diff import DecisionDiff, PopulationDiff, diff_plans
from devteam_harness.minimal_fix import (
    Baseline,
    Candidate,
    Outcome,
    Scenario,
    dependency_candidates,
    evaluate,
    generate_candidates,
    priority_candidates,
    render_ranking,
    search,
    threshold_candidates,
)

PACK: dict[str, Any] = {
    "pack_id": "pack:test",
    "rules": [
        {
            "id": "r:policy",
            "predicate": {"signal": "policy_state", "op": "lte", "value": "verbal"},
            "effect": {
                "plan_seed": {
                    "id": "seed:draft_policies",
                    "urgency": "high",
                    "depends_on": ["seed:formalize"],
                }
            },
        },
        {
            "id": "r:composite",
            "predicate": {
                "all": [
                    {"signal": "has_gov_clients", "op": "eq", "value": True},
                    {"signal": "org_structure_state", "op": "eq", "value": "absent"},
                ]
            },
            "effect": {"flags_gap": {"gap_id": "gap:x", "severity": "critical"}},
        },
    ],
}


def _item(task: str, **fields: Any) -> dict[str, Any]:
    base = {"id": task, "priority": "high", "timeframe_bucket": "week_1", "effort_size": "small"}
    base.update(fields)
    return base


# --- Decision Diff --------------------------------------------------------------------------


def test_a_diff_names_what_changed_not_what_the_plans_are() -> None:
    diff = diff_plans(
        [_item("a"), _item("b", priority="medium")],
        [_item("b", priority="high"), _item("c")],
    )
    assert diff.added == ["c"]
    assert diff.removed == ["a"]
    assert any(change.attribute == "priority" for change in diff.changes)


def test_reordering_the_same_plan_is_not_a_change() -> None:
    """Two plans holding the same tasks in a different list order are the same ADVICE. Reporting
    that would bury the real differences."""
    assert diff_plans([_item("a"), _item("b")], [_item("b"), _item("a")]).empty


def test_a_schedule_move_is_reported() -> None:
    diff = diff_plans([_item("a", timeframe_bucket="week_1")], [_item("a", timeframe_bucket="year_1")])
    assert diff.changes[0].attribute == "schedule"


def test_a_dependency_change_is_reported() -> None:
    diff = diff_plans(
        [_item("a", depends_on_item_ids=["x"])], [_item("a", depends_on_item_ids=[])]
    )
    assert diff.changes[0].attribute == "dependencies"


def test_magnitude_ranks_a_smaller_change_as_smaller() -> None:
    """Between two changes that fix the same defect, the one that disturbs less is safer."""
    small = diff_plans([_item("a")], [_item("a", priority="low")])
    large = diff_plans([_item("a")], [_item("b"), _item("c")])
    assert small.magnitude < large.magnitude


def test_a_population_diff_aggregates_without_losing_the_examples() -> None:
    population = PopulationDiff()
    population.add(1, diff_plans([_item("a")], [_item("a")]))
    population.add(2, diff_plans([_item("a")], [_item("b")]))
    assert population.scenarios == 2
    assert population.unchanged == 1
    assert population.affected == 1
    assert "seed 2" in population.render()


# --- the search space is exactly what a product owner owns ------------------------------------


def test_threshold_candidates_walk_operators_and_ladder_values() -> None:
    candidates = threshold_candidates(PACK)
    described = {candidate.description for candidate in candidates}
    assert any("policy_state gte documented_unapproved" in d for d in described)
    assert all(candidate.space == "threshold" for candidate in candidates)


def test_predicates_nested_under_all_are_reachable() -> None:
    """A flat scan would miss composite rules — exactly the ones expressing the most interesting
    conditions."""
    assert any("org_structure_state" in c.description for c in threshold_candidates(PACK))


def test_priority_candidates_cover_every_other_urgency() -> None:
    candidates = priority_candidates(PACK)
    assert {c.description.split()[-1] for c in candidates} == {"critical", "medium", "low"}


def test_dependency_candidates_only_REMOVE() -> None:
    """Adding a dependency requires knowing which prerequisite is meant — a domain judgement a
    search must not guess at."""
    candidates = dependency_candidates(PACK)
    assert candidates and all("drop dependency" in c.description for c in candidates)


def test_nothing_outside_the_owner_s_space_is_generated() -> None:
    """No code, no engine changes — only pack data, so every candidate is reviewable as a JSON
    diff and the worst a bad one can do is be rejected."""
    assert {c.space for c in generate_candidates(PACK)} <= {"threshold", "priority", "dependency"}


# --- nothing is written ------------------------------------------------------------------------


def test_applying_a_candidate_never_mutates_the_input_pack() -> None:
    """Changing a governance rule is the owner's decision. This proposes and measures; it must
    never adopt."""
    original = copy.deepcopy(PACK)
    candidate = threshold_candidates(PACK)[0]

    evaluate(
        candidate,
        [Scenario(seed=1, signals={}, value_types={})],
        PACK,
        Baseline(findings={1: []}, plans={1: []}),
        analyse=lambda _pack, _scenario: _Applicability([]),
    )
    assert PACK == original, "the pack passed in must be untouched"


def test_the_real_pack_file_is_never_opened_for_writing() -> None:
    """A guard on the promise in the module docstring: core.json is never modified."""
    source = pathlib.Path("devteam_harness/minimal_fix.py").read_text(encoding="utf-8")
    assert "write_text" not in source
    assert "open(" not in source


# --- scoring -----------------------------------------------------------------------------------


class _Applicability:
    def __init__(self, task_ids: list[str]) -> None:
        self.plan_items = [{"id": task} for task in task_ids]
        self.gaps: list[dict[str, Any]] = []
        # A zero-star dimension is what makes an empty plan a FINDING; without it there is no
        # baseline defect for a candidate to fix.
        self.maturity: dict[str, Any] = {"governance": {"stars": 0}}
        self.capacity: dict[str, Any] = {}


def _outcome(fixed: int, introduced: int, blast: int = 0) -> Outcome:
    return Outcome(
        candidate=Candidate("threshold", "r", "d", lambda _doc: None),
        fixed={"rule": fixed} if fixed else {},
        introduced={"other": introduced} if introduced else {},
        plans_changed=blast,
    )


def test_a_regression_is_not_cancelled_out_by_a_fix() -> None:
    """Fixing six and breaking one is NOT a net win of five: a regression ships a NEW defect to
    organizations that were previously fine, which is worse than leaving a known one in place."""
    assert _outcome(6, 1).score < _outcome(3, 0).score


def test_a_clean_fix_beats_a_larger_dirty_one() -> None:
    assert _outcome(3, 0).score > _outcome(10, 4).score


def test_blast_radius_breaks_ties_between_equally_clean_fixes() -> None:
    assert _outcome(3, 0, blast=10).score > _outcome(3, 0, blast=200).score


def test_clean_means_benefit_without_regression() -> None:
    assert _outcome(3, 0).clean
    assert not _outcome(3, 1).clean
    assert not _outcome(0, 0).clean


def test_a_candidate_that_breaks_the_engine_is_scored_as_a_regression() -> None:
    """An edit that crashes the planner must never rank above one that works."""

    def explode(_pack: dict[str, Any], _scenario: Scenario) -> Any:
        raise ValueError("bad predicate")

    outcome = evaluate(
        threshold_candidates(PACK)[0],
        [Scenario(seed=1, signals={}, value_types={})],
        PACK,
        Baseline(findings={1: []}, plans={1: []}),
        analyse=explode,
    )
    assert outcome.introduced == {"candidate_crashed_the_engine": 1}
    assert not outcome.clean


# --- the search ----------------------------------------------------------------------------------


def test_search_returns_only_candidates_that_fix_the_target() -> None:
    scenarios = [Scenario(seed=1, signals={}, value_types={"policy_state": "enum"})]

    def analyse(pack: dict[str, Any], _scenario: Scenario) -> _Applicability:
        # Baseline: empty plan (a finding). Any candidate that widens the rule yields a task.
        widened = pack["rules"][0]["predicate"]["value"] != "verbal"
        return _Applicability(["seed:draft_policies"] if widened else [])

    outcomes = search(
        scenarios,
        PACK,
        analyse=analyse,
        target_rule="an_immature_organization_gets_a_plan",
        limit=40,
    )
    assert outcomes, "at least one widening must fix the empty plan"
    assert all(o.fixed.get("an_immature_organization_gets_a_plan") for o in outcomes)


def test_search_ranks_best_first() -> None:
    scenarios = [Scenario(seed=1, signals={}, value_types={})]
    outcomes = search(scenarios, PACK, analyse=lambda _p, _s: _Applicability([]), limit=10)
    scores = [outcome.score for outcome in outcomes]
    assert scores == sorted(scores, reverse=True)


def test_an_empty_ranking_says_so_rather_than_pretending() -> None:
    assert "no candidate improved anything" in render_ranking([])


def test_the_pack_shape_this_searches_matches_the_real_one() -> None:
    """Guards against the search silently going blind if the pack format changes."""
    real = pathlib.Path(
        "../../../v2/packages/governance-discovery/governance_discovery/packs/core.json"
    )
    if not real.is_file():  # pragma: no cover - only outside the monorepo
        return
    document = json.loads(real.read_text(encoding="utf-8"))
    assert threshold_candidates(document), "no threshold candidate found in the real pack"
    assert priority_candidates(document), "no priority candidate found in the real pack"


def test_a_diff_is_used_to_measure_blast_radius() -> None:
    """Blast radius must count plans whose ADVICE changed, not plans that were re-serialised."""
    assert isinstance(diff_plans([_item("a")], [_item("a")]), DecisionDiff)
    assert diff_plans([_item("a")], [_item("a")]).magnitude == 0


# --- intent is part of the ranking (Rule Intent Verifier) ---------------------------------------


def test_a_semantically_destructive_candidate_sinks_below_a_faithful_one() -> None:
    """The finder's own top candidate fixed 3 defects with zero regression by making the rule fire
    for everyone. Statistically excellent, semantically vandalism — it must not lead."""
    from devteam_harness.intent import IntentVerdict, SemanticDistance

    vandal = _outcome(3, 0)
    vandal.intent = IntentVerdict(distance=SemanticDistance.HIGH, reasons=["fires for everyone"])
    faithful = _outcome(1, 0)

    assert vandal.score < faithful.score
    assert not vandal.clean, "a rule-destroying edit is never 'clean'"


def test_clean_requires_intent_preserved_not_just_zero_regression() -> None:
    from devteam_harness.intent import IntentVerdict, SemanticDistance

    outcome = _outcome(5, 0)
    outcome.intent = IntentVerdict(distance=SemanticDistance.MEDIUM, reasons=["drifted"])
    assert outcome.regression == 0
    assert not outcome.clean


def test_only_threshold_edits_are_judged_for_intent() -> None:
    """A priority change or a dropped dependency alters what a rule DOES, never the population it
    applies to — judging them by selectivity would invent findings."""
    from devteam_harness.minimal_fix import _verify_intent

    priority = priority_candidates(PACK)[0]
    assert _verify_intent(priority, PACK, {}, {}).distance.value == "none"
