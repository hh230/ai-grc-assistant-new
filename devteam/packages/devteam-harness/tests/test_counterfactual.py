"""Tests for the Counterfactual Judge.

The rules here are about the SHAPE of the decision function, so each test constructs a `replan`
that produces a known shape. No engine, no interview — the properties being pinned are about
comparison and classification, which is where a sensitivity analyser goes wrong.
"""

from __future__ import annotations

from typing import Any

from devteam_harness.investigation.counterfactual import (
    IMPROVEMENT_CHURN_LIMIT,
    Perturbation,
    PlanShape,
    all_perturbations,
    analyse_sensitivity,
    domain_of,
    find_ignored_signals,
    judge_change,
    ladder_perturbations,
    near_miss_perturbations,
)


class _Applicability:
    def __init__(self, task_ids: list[str]) -> None:
        self.plan_items = [{"id": task, "priority": "high"} for task in task_ids]


def _shape(*tasks: str) -> PlanShape:
    return PlanShape(task_ids=frozenset(tasks), priorities={task: "high" for task in tasks})


# --- what gets probed ---------------------------------------------------------------------------


def test_a_maturity_signal_is_probed_one_rung_UP() -> None:
    """The organization improving slightly is the interesting direction: it is where a plan can
    wrongly collapse."""
    perturbations = ladder_perturbations({"policy_state": "verbal"})
    assert [p.after for p in perturbations] == ["documented_unapproved"]


def test_the_top_of_the_ladder_has_nothing_above_it() -> None:
    assert ladder_perturbations({"policy_state": "reviewed_periodically"}) == []


def test_numeric_answers_are_probed_by_ONE() -> None:
    """The 45 → 46 probe. A one-unit difference must never restructure advice."""
    afters = {p.after for p in near_miss_perturbations({"employee_count": 45})}
    assert afters == {44, 46}


def test_a_boolean_is_not_treated_as_a_number() -> None:
    """`True + 1` is 2 in Python — a probe that would be nonsense."""
    assert near_miss_perturbations({"has_board": True}) == []


def test_every_probe_changes_exactly_one_signal() -> None:
    signals = {"policy_state": "verbal", "has_board": True, "employee_count": 45}
    for perturbation in all_perturbations(signals):
        assert perturbation.signal in signals
        assert perturbation.after != perturbation.before


# --- the three shapes ---------------------------------------------------------------------------


def test_an_improvement_that_empties_the_plan_is_reported() -> None:
    """The organization improves by one step and is told it has nothing to do."""
    findings = judge_change(
        Perturbation("policy_state", "verbal", "documented_unapproved"), _shape("a", "b"), _shape()
    )
    assert findings and findings[0].kind == "improvement_empties_the_plan"


def test_a_boolean_that_removes_its_own_task_is_NOT_reported() -> None:
    """`handles_personal_data: True → False` legitimately removes the personal-data task: fewer
    obligations, fewer tasks. The first version reported 15 of these — correct behaviour dressed
    up as a defect."""
    findings = judge_change(
        Perturbation("handles_personal_data", True, False), _shape("review_pii"), _shape()
    )
    assert findings == []


def test_a_one_unit_numeric_change_that_alters_the_plan_is_a_cliff() -> None:
    findings = judge_change(
        Perturbation("employee_count", 45, 46), _shape("a"), _shape("a", "b")
    )
    assert findings and findings[0].kind == "threshold_cliff"


def test_a_one_unit_numeric_change_that_alters_nothing_is_fine() -> None:
    assert judge_change(Perturbation("employee_count", 45, 46), _shape("a"), _shape("a")) == []


def test_a_single_rung_improvement_may_adapt_the_plan_but_not_replace_it() -> None:
    before, after = _shape("a", "b", "c", "d"), _shape("w", "x", "y", "z")
    findings = judge_change(Perturbation("policy_state", "verbal", "approved"), before, after)
    assert findings and findings[0].kind == "improvement_replaces_the_plan"
    assert before.churn(after) > IMPROVEMENT_CHURN_LIMIT


def test_a_modest_adaptation_is_not_reported() -> None:
    findings = judge_change(
        Perturbation("policy_state", "verbal", "approved"),
        _shape("a", "b", "c", "d"),
        _shape("a", "b", "c", "e"),
    )
    assert findings == []


# --- inertness is a property of a SIGNAL, not of one step ---------------------------------------


def test_a_signal_that_never_changes_the_plan_is_reported() -> None:
    """The finding that landed live: `has_gov_clients` produced a byte-identical plan for every
    value it can take, on 120 of 120 organizations."""
    findings = find_ignored_signals(
        {"has_gov_clients": True}, lambda _signals: _Applicability(["a", "b"])
    )
    assert findings and findings[0].kind == "consequential_answer_ignored"
    assert "every value it can take" in findings[0].detail


def test_a_signal_that_matters_at_SOME_value_is_not_reported() -> None:
    """The first version asked "did this one step change anything" and produced 412 findings on
    120 organizations, most of them correct behaviour: `policy_state` moving from
    documented_unapproved to approved changes nothing, yet plainly drives the plan elsewhere."""

    def replan(signals: dict[str, Any]) -> _Applicability:
        return _Applicability(["draft"] if signals["policy_state"] == "absent" else [])

    assert find_ignored_signals({"policy_state": "approved"}, replan) == []


def test_a_ladder_signal_is_probed_across_its_whole_domain() -> None:
    assert len(domain_of("policy_state", "verbal")) == 5


def test_a_boolean_domain_is_both_values() -> None:
    assert sorted(domain_of("has_board", True), key=str) == [False, True]


def test_an_unknown_signal_has_no_domain_to_probe() -> None:
    """Inventing a domain would invent findings."""
    assert domain_of("primary_activity", "construction") == []


# --- the sweep ----------------------------------------------------------------------------------


def test_a_perturbation_that_crashes_the_planner_is_itself_a_finding() -> None:
    """An input the product cannot survive is a defect, not a reason to abandon the run."""

    def replan(signals: dict[str, Any]) -> _Applicability:
        if signals["employee_count"] == 46:
            raise ValueError("boom")
        return _Applicability(["a"])

    report = analyse_sensitivity(1, {"employee_count": 45}, replan)
    assert any(f.kind == "perturbation_crashed" for f in report.findings)


def test_a_stable_decision_surface_produces_no_findings() -> None:
    """The rules must stay quiet on a well-behaved planner."""

    def replan(signals: dict[str, Any]) -> _Applicability:
        return _Applicability(["a"] if signals["policy_state"] == "absent" else ["b"])

    report = analyse_sensitivity(1, {"policy_state": "verbal"}, replan)
    assert report.ok, report.render()
