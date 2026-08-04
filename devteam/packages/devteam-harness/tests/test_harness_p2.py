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


# --- the real defect this harness found, and its fix ------------------------------------------


def test_no_plan_references_an_item_it_does_not_contain() -> None:
    """The defect this harness was built to catch, now asserted as FIXED.

    A plan item declared `depends_on` a seed whose own rule never fired, leaving a reference that
    resolves to nothing. It failed on ~15% of generated organizations.

    This test previously asserted the OPPOSITE — that the defect was still detectable — with a
    docstring saying "when the pack is fixed, this test is what proves the fix". It duly went red
    the moment the scheduler was fixed, which is exactly what a tripwire is for. Turned around
    rather than deleted, so the population sweep keeps guarding the fix: a rule that reintroduces
    an unconditional dependency, or a scheduler that stops filtering, fails here immediately.

    Root cause and fix: `governance_discovery/scheduler.py::_as_item`.
    """
    summary, store = run_campaign(count=200)
    seeds = store.failing_seeds(summary.run_id, name="plan_dependencies_exist")
    store.close()
    assert not seeds, f"a plan referenced a missing item; reproduce with --seed {seeds[:3]}"


def test_the_dangling_dependency_invariant_is_still_wired_up() -> None:
    """Guards the guard.

    A population that passes proves nothing if the check was quietly removed — "no violations"
    and "no checking" look identical from the outside. This asserts the invariant still exists and
    still fires, by handing it a plan that genuinely is inconsistent.
    """
    from types import SimpleNamespace

    from devteam_harness.invariants import _plan_dependencies_exist

    inconsistent = SimpleNamespace(
        plan_items=[
            {"id": "seed:a", "depends_on_item_ids": ["seed:ghost"]},
        ]
    )
    violations = _plan_dependencies_exist(inconsistent)
    assert violations, "the invariant no longer fires on a genuinely inconsistent plan"
    assert violations[0].name == "plan_dependencies_exist"
    assert "depends on missing" in violations[0].detail
