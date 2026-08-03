"""P2 tests — invariants, persistence, and seed-based reproduction."""

from __future__ import annotations

from devteam_harness import ResultStore, check_scenario, run_campaign
from devteam_harness.invariants import Violation, check_transcript
from devteam_harness.runner import Turn

# --- invariant evaluation --------------------------------------------------------------------


def test_a_clean_scenario_reports_its_violations_explicitly() -> None:
    """A scenario carries its verdict; nothing is inferred from an exception not being raised."""
    checked = check_scenario(0)
    assert checked.result.concluded
    assert all(isinstance(v, Violation) for v in checked.violations)


def test_transcript_invariants_catch_a_repeated_question() -> None:
    turns = [
        Turn(1, "q:a", "boolean", True, True, False),
        Turn(2, "q:a", "boolean", True, False, False),
    ]
    names = {v.name for v in check_transcript(turns)}
    assert "no_question_asked_twice" in names


def test_transcript_invariants_catch_a_skipped_required_question() -> None:
    turns = [Turn(1, "q:a", "boolean", True, None, True)]
    names = {v.name for v in check_transcript(turns)}
    assert "required_questions_never_skipped" in names


# --- persistence -----------------------------------------------------------------------------


def test_a_campaign_persists_every_scenario() -> None:
    summary, store = run_campaign(count=25)
    assert summary.scenarios == 25
    assert summary.passed + summary.failed == 25
    store.close()


def test_violations_are_queryable_by_name() -> None:
    summary, store = run_campaign(count=60)
    for name, total in summary.violations_by_name.items():
        assert total > 0
        assert store.failing_seeds(summary.run_id, name=name), f"{name} has no reproducible seed"
    store.close()


def test_results_survive_in_a_real_file(tmp_path: object) -> None:
    """The store must be a real database on disk, not an in-process convenience."""
    path = f"{tmp_path}/harness.db"
    summary, store = run_campaign(count=10, store=ResultStore(path))
    store.close()

    reopened = ResultStore(path)
    persisted = reopened.summary(summary.run_id)
    assert persisted.scenarios == 10
    assert persisted.passed + persisted.failed == 10
    reopened.close()


# --- reproduction: the whole point of storing seeds ------------------------------------------


def test_a_reported_seed_reproduces_the_identical_verdict() -> None:
    summary, store = run_campaign(count=80)
    seeds = store.failing_seeds(summary.run_id)
    store.close()
    if not seeds:  # nothing failing to reproduce is a valid state, not a broken test
        return
    seed = seeds[0]
    first = check_scenario(seed)
    second = check_scenario(seed)
    assert [(v.name, v.detail) for v in first.violations] == [
        (v.name, v.detail) for v in second.violations
    ]


# --- the known real defect this harness found -------------------------------------------------


def test_dangling_plan_dependencies_are_detected_and_reproducible() -> None:
    """Documents a REAL product defect (not a harness artifact): a plan seed may declare
    `depends_on` a seed whose own rule never fired, leaving a task blocked on a prerequisite that
    will never exist. Asserting it is detectable keeps the finding from silently disappearing —
    when the pack is fixed, this test is what proves the fix.
    """
    summary, store = run_campaign(count=200)
    seeds = store.failing_seeds(summary.run_id, name="plan_dependencies_exist")
    store.close()
    assert seeds, "expected the known dangling-dependency defect to be detected"

    checked = check_scenario(seeds[0])
    details = [v.detail for v in checked.violations if v.name == "plan_dependencies_exist"]
    assert details and "depends on missing" in details[0]
