"""The ChainDriver policy: watch a branch's CI and, on red, advance the correlated chain until green
or exhausted. Deterministic — a real GitHubActions is driven by a canned CommandRunner (no network),
and the mission opener is a fake that records the attempts it is asked to open. The tests exercise
the POLICY (green stops, pending waits, red advances, the cap alerts), not any GitHub parsing.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from devteam_chain import AttemptStore, ChainAttempt
from devteam_contracts import platform_tenant
from devteam_github import GitHubActions, WorkflowRun
from devteam_runtime import ChainDriver, ChainStatus, build_chain_driver
from devteam_tools import CommandResult
from mission_engine.lifecycle import MissionStatus
from mission_engine.mission import Mission


def _runs_json(status: str, conclusion: str) -> str:
    return json.dumps(
        {
            "workflow_runs": [
                {
                    "id": 7,
                    "name": "CI",
                    "status": status,
                    "conclusion": conclusion,
                    "head_branch": "pr-1",
                    "display_title": "fix",
                    "html_url": "https://gh/7",
                }
            ]
        }
    )


_RED = _runs_json("completed", "failure")
_GREEN = _runs_json("completed", "success")
_RUNNING = _runs_json("in_progress", "")
_NO_RUNS = json.dumps({"workflow_runs": []})


class AlwaysRunner:
    """A CommandRunner that returns the same canned stdout for every call (the watch query)."""

    def __init__(self, stdout: str) -> None:
        self._stdout = stdout
        self.calls = 0

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        self.calls += 1
        return CommandResult(0, self._stdout, "")


class QueueRunner:
    """Pops queued CommandResults in call order — for the curl sequence (runs, jobs, log)."""

    def __init__(self, results: Sequence[CommandResult] | None = None) -> None:
        self._results = list(results or [])
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        self.calls.append((tuple(args), stdin))
        return self._results.pop(0) if self._results else CommandResult(0, "", "")


def _github(stdout: str) -> GitHubActions:
    return GitHubActions(AlwaysRunner(stdout), "o/r", token="t")


class RecordingOpener:
    """Records the (correlation_ref, attempt_number) it is asked to open and returns a real Mission
    (CREATED) — the fake seam so the policy is tested without logs / analysis / DB."""

    def __init__(self) -> None:
        self.opened: list[tuple[str, int]] = []

    def __call__(self, run: WorkflowRun, correlation_ref: str, number: int) -> Mission | None:
        self.opened.append((correlation_ref, number))
        return Mission.create(goal=f"fix (attempt {number})", tenant=platform_tenant())


def _finished_now(attempt: ChainAttempt) -> bool:
    return True  # each attempt reads as finished between advances (so the chain moves on each red)


class Finishing:
    """Controls whether the latest attempt reads as finished — flip ``done`` to let the chain open
    the next attempt, mirroring a human approving/rejecting the gated mission. Reads the attempt."""

    def __init__(self, done: bool = False) -> None:
        self.done = done

    def __call__(self, attempt: ChainAttempt) -> bool:
        return self.done


def test_green_ci_resolves_the_chain_without_opening_a_mission() -> None:
    store, opener = AttemptStore(), RecordingOpener()
    driver = ChainDriver(_github(_GREEN), store, opener, is_finished=_finished_now)
    outcome = driver.advance("issue-1", "pr-1")
    assert outcome.status is ChainStatus.GREEN
    assert opener.opened == []  # nothing opened
    assert store.count("issue-1") == 0


def test_pending_ci_keeps_watching_without_opening_a_mission() -> None:
    for stdout in (_RUNNING, _NO_RUNS):  # still running, and no run yet
        store, opener = AttemptStore(), RecordingOpener()
        driver = ChainDriver(_github(stdout), store, opener, is_finished=_finished_now)
        outcome = driver.advance("issue-1", "pr-1")
        assert outcome.status is ChainStatus.PENDING
        assert opener.opened == [] and store.count("issue-1") == 0


def test_red_ci_under_the_cap_opens_the_next_correlated_attempt() -> None:
    store, opener = AttemptStore(), RecordingOpener()
    driver = ChainDriver(_github(_RED), store, opener, is_finished=_finished_now, max_attempts=3)
    outcome = driver.advance("issue-1", "pr-1")
    assert outcome.status is ChainStatus.OPENED
    assert outcome.attempt is not None
    assert (outcome.attempt.correlation_ref, outcome.attempt.attempt_number) == ("issue-1", 1)
    assert outcome.mission is not None  # the opener's mission rides the outcome
    assert outcome.attempt.mission_id == outcome.mission.id  # the record links to its mission
    assert opener.opened == [("issue-1", 1)]
    # the store is the SSoT: the recorded attempt carries the mission_id the Driver reads back
    assert store.latest("issue-1") == outcome.attempt


def test_chain_advances_attempts_then_alerts_at_the_cap() -> None:
    store, opener = AttemptStore(), RecordingOpener()
    driver = ChainDriver(_github(_RED), store, opener, is_finished=_finished_now, max_attempts=3)

    numbers: list[int] = []
    for _ in range(3):  # three red rounds, each attempt finishing before the next, open 1, 2, 3
        outcome = driver.advance("issue-1", "pr-1")
        assert outcome.status is ChainStatus.OPENED
        assert outcome.attempt is not None
        numbers.append(outcome.attempt.attempt_number)
    assert numbers == [1, 2, 3]

    outcome = driver.advance("issue-1", "pr-1")  # the fourth red round stops the chain
    assert outcome.status is ChainStatus.EXHAUSTED
    assert outcome.mission is None  # an alert, not another mission
    assert outcome.alert is not None
    assert outcome.alert.attempts == 3
    assert "human intervention" in outcome.alert.reason
    assert len(opener.opened) == 3  # only three missions were ever opened
    assert store.count("issue-1") == 3


def test_advance_waits_while_the_current_attempt_is_in_flight() -> None:
    # The core idempotency rule: one in-flight attempt per chain. While attempt 1's mission is
    # unfinished, every red poll returns PENDING — NO new attempt, no matter how long CI stays red.
    store, opener = AttemptStore(), RecordingOpener()
    open_forever = Finishing(done=False)  # the attempt never finishes
    driver = ChainDriver(_github(_RED), store, opener, is_finished=open_forever, max_attempts=3)

    first = driver.advance("issue-1", "pr-1")
    assert first.status is ChainStatus.OPENED and first.attempt is not None
    assert first.attempt.attempt_number == 1
    for _ in range(5):  # CI stays red, but the attempt is still open
        outcome = driver.advance("issue-1", "pr-1")
        assert outcome.status is ChainStatus.PENDING
    assert store.count("issue-1") == 1  # still just the one attempt — not a poll counter
    assert len(opener.opened) == 1


def test_a_new_attempt_opens_only_after_the_previous_finishes() -> None:
    store, opener = AttemptStore(), RecordingOpener()
    gate = Finishing(done=False)
    driver = ChainDriver(_github(_RED), store, opener, is_finished=gate, max_attempts=3)

    assert driver.advance("issue-1", "pr-1").status is ChainStatus.OPENED  # attempt 1
    assert driver.advance("issue-1", "pr-1").status is ChainStatus.PENDING  # still in flight
    gate.done = True  # attempt 1 finishes (approved / rejected / …); CI is still red
    second = driver.advance("issue-1", "pr-1")
    assert second.status is ChainStatus.OPENED and second.attempt is not None
    assert second.attempt.attempt_number == 2
    assert opener.opened == [("issue-1", 1), ("issue-1", 2)]


def test_isolated_chains_advance_independently() -> None:
    store, opener = AttemptStore(), RecordingOpener()
    driver = ChainDriver(_github(_RED), store, opener, is_finished=_finished_now, max_attempts=3)
    driver.advance("issue-1", "pr-1")
    driver.advance("issue-1", "pr-1")
    outcome = driver.advance("issue-2", "pr-2")  # a different chain starts at attempt 1
    assert outcome.attempt is not None
    assert (outcome.attempt.correlation_ref, outcome.attempt.attempt_number) == ("issue-2", 1)
    assert store.count("issue-1") == 2 and store.count("issue-2") == 1


def test_green_after_reds_stops_the_chain_with_history_intact() -> None:
    store, opener = AttemptStore(), RecordingOpener()
    red = ChainDriver(_github(_RED), store, opener, is_finished=_finished_now)
    red.advance("issue-1", "pr-1")  # attempt 1 opened
    green = ChainDriver(_github(_GREEN), store, opener, is_finished=_finished_now)
    outcome = green.advance("issue-1", "pr-1")
    assert outcome.status is ChainStatus.GREEN
    assert store.count("issue-1") == 1  # the attempt made stays in the history
    assert opener.opened == [("issue-1", 1)]


def test_build_chain_driver_opens_a_real_gated_mission_from_a_red_run(tmp_path: Path) -> None:
    # The production wiring end to end (deterministic): a red PR run drives the real opener —
    # find the failing step, download the log, normalize, Developer proposes a diff, pause at gate.
    jobs = json.dumps(
        {
            "jobs": [
                {
                    "id": 200,
                    "name": "python",
                    "conclusion": "failure",
                    "steps": [{"number": 6, "name": "Run uv run mypy .", "conclusion": "failure"}],
                }
            ]
        }
    )
    log = "2024-01-01T00:00:01Z src/x.py:3: error: Missing return type  [no-untyped-def]\n"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def f():\n    pass\n    return None\n")  # line 3
    github = GitHubActions(
        QueueRunner(
            [
                CommandResult(0, _RED, ""),  # advance 1: latest_run_for_branch
                CommandResult(0, jobs, ""),  # advance 1: find_failing_step
                CommandResult(0, log, ""),  # advance 1: download_job_log
                CommandResult(0, _RED, ""),  # advance 2: latest_run_for_branch (still red)
            ]
        ),
        "o/r",
        token="t",
    )
    driver = build_chain_driver(github, repo_root=tmp_path, git_runner=QueueRunner())

    first = driver.advance("issue-1", "pr-1")
    assert first.status is ChainStatus.OPENED
    assert first.attempt is not None and first.attempt.attempt_number == 1
    assert first.mission is not None
    assert first.attempt.mission_id == first.mission.id  # the recorded attempt links to its mission
    assert first.mission.status is MissionStatus.AWAITING_APPROVAL  # paused at the human gate
    output = first.mission.step_results[0].output  # the Developer's real proposal
    assert "```diff" in output and "type: ignore[no-untyped-def]" in output

    # Second poll, CI still red, but the gated mission is unfinished → the REAL is_finished (reading
    # the shared mission store) keeps the chain PENDING; it does NOT open a second mission.
    second = driver.advance("issue-1", "pr-1")
    assert second.status is ChainStatus.PENDING
