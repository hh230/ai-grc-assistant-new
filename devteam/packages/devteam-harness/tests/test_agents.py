"""P3 tests — the QA agent team."""

from __future__ import annotations

from devteam_harness.agents import breaker, explorer, regression, verifier
from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.agents.reporter import compile_report
from devteam_harness.agents.team import run_team

# --- breaker: the adversary -------------------------------------------------------------------


def test_breaker_actually_attacks() -> None:
    report = breaker.run(0)
    assert report.stats["hostile_inputs_tried"] >= len(breaker.HOSTILE_VALUES)
    assert report.stats["protocol_abuses_tried"] >= 4


def test_hostile_input_is_always_rejected_with_a_typed_error() -> None:
    """The service contracts that no raw exception ever reaches a caller. An untyped escape
    would surface as an unhandled 500 from the API."""
    for seed in range(20):
        report = breaker.run(seed)
        crashes = [f for f in report.findings if f.kind == "untyped_exception"]
        assert not crashes, f"seed {seed}: {[c.detail for c in crashes]}"


def test_a_rejected_input_never_destroys_the_session() -> None:
    for seed in range(10):
        report = breaker.run(seed)
        assert not [f for f in report.findings if f.kind == "session_lost"]


# --- explorer: coverage, not volume -----------------------------------------------------------


def test_explorer_measures_real_coverage() -> None:
    report, coverage = explorer.run(count=40)
    assert report.stats["distinct_questions"] > 0
    assert report.stats["distinct_question_answers"] >= report.stats["distinct_questions"]
    assert coverage.paths


def test_explorer_flags_saturation_when_a_window_teaches_nothing() -> None:
    """The point of the agent: say when more scenarios stop buying coverage.

    Re-exploring an already-covered seed range is the deterministic way to force a plateau —
    every pair is already known, so the whole final window gains nothing.
    """
    report, coverage = explorer.run(count=12, start_seed=0, window=12)
    assert report.stats["coverage_gained_in_final_window"] > 0  # a fresh range must teach us something

    # Re-walking the same seeds with the accumulated coverage gains nothing new — a real plateau.
    repeat, _ = explorer.run(count=12, start_seed=0, window=12, coverage=coverage)
    assert repeat.stats["coverage_gained_in_final_window"] == 0
    assert any(f.kind == "coverage_plateau" for f in repeat.findings)


# --- verifier: one definition of correct ------------------------------------------------------


def test_verifier_reports_violations_with_reproduction_steps() -> None:
    report = verifier.run(count=40)
    assert report.stats["scenarios"] == 40
    for finding in report.findings:
        assert finding.seed is not None
        assert "--seed" in finding.reproduce


# --- regression: the release gate -------------------------------------------------------------


def test_regression_replays_and_classifies() -> None:
    known_bad = [1, 8, 11]
    report, outcome = regression.run(known_bad)
    assert report.stats["replayed"] == len(known_bad)
    assert len(outcome.still_failing) + len(outcome.now_passing) == len(known_bad)


def test_regression_on_a_clean_seed_reports_it_as_passing() -> None:
    _report, outcome = regression.run([0])
    assert outcome.now_passing == [0]
    assert outcome.still_failing == []


# --- reporter: usable output ------------------------------------------------------------------


def test_reporter_groups_by_class_and_keeps_one_repro_each() -> None:
    findings = [
        Finding("a", Severity.INVARIANT, "dup", "first", "cmd-1", 1),
        Finding("b", Severity.INVARIANT, "dup", "second", "cmd-2", 2),
        Finding("a", Severity.CRASH, "boom", "kaboom", "cmd-3", 3),
    ]
    report = compile_report([AgentReport(agent="a", findings=findings)])
    assert report.total_findings == 3
    assert len(report.classes) == 2
    # Crashes outrank invariant violations.
    assert report.classes[0].kind == "boom"
    duplicates = next(c for c in report.classes if c.kind == "dup")
    assert duplicates.count == 2
    assert duplicates.reproduce == "cmd-1"
    assert duplicates.seeds == [1, 2]


def test_reporter_renders_a_clean_run_honestly() -> None:
    report = compile_report([AgentReport(agent="verifier", stats={"scenarios": 5})])
    assert report.ok
    assert "no findings" in report.render()


# --- the team ---------------------------------------------------------------------------------


def test_the_team_runs_every_agent_and_produces_one_report() -> None:
    outcome = run_team(count=30, breaker_samples=5)
    agents = {r.agent for r in outcome.reports}
    assert {"explorer", "breaker", "verifier"} <= agents
    rendered = outcome.report.render()
    assert "[explorer]" in rendered and "[breaker]" in rendered and "[verifier]" in rendered
