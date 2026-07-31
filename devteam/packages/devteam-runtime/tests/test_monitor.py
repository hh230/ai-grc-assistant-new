"""The ContinuousMonitor Worker: a pure scheduler that advances every open PR's chain each pass.

Deterministic and no-network — a real GitHubActions is driven by a routing CommandRunner (canned
/pulls list + per-branch run state), a real ChainDriver sits behind it, and sleep is injected. The
tests exercise the SCHEDULER: it advances each open PR once, does nothing extra for GREEN/PENDING/
OPENED, records the alert on EXHAUSTED, survives one PR's error, and loops tick->sleep until stop.
No policy is tested here — that lives in the ChainDriver.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from devteam_chain import AttemptStore, ChainAlert, ChainAttempt
from devteam_contracts import platform_tenant
from devteam_github import GitHubActions, WorkflowRun
from devteam_runtime import ChainDriver, ChainStatus, ContinuousMonitor
from devteam_tools import CommandResult
from mission_engine.mission import Mission


def _runs(status: str, conclusion: str) -> str:
    return json.dumps(
        {
            "workflow_runs": [
                {
                    "id": 7,
                    "name": "CI",
                    "status": status,
                    "conclusion": conclusion,
                    "head_branch": "b",
                    "display_title": "t",
                    "html_url": "u",
                }
            ]
        }
    )


_GREEN = _runs("completed", "success")
_RED = _runs("completed", "failure")
_RUNNING = _runs("in_progress", "")


def _pulls_json(*prs: tuple[int, str]) -> str:
    return json.dumps(
        [
            {"number": n, "head": {"ref": b}, "title": f"PR {n}", "html_url": f"u/{n}"}
            for n, b in prs
        ]
    )


class RoutingRunner:
    """Routes canned responses by URL: the /pulls list, or a branch's run state. Optionally fails a
    branch's query (curl exit 7) so a single PR errors while the rest of the pass keeps going."""

    def __init__(
        self, pulls: str, states: dict[str, str], *, fail_branches: frozenset[str] = frozenset()
    ) -> None:
        self._pulls = pulls
        self._states = states
        self._fail = fail_branches
        self.pull_calls = 0

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        url = args[-1]
        if "/pulls" in url:
            self.pull_calls += 1
            return CommandResult(0, self._pulls, "")
        for branch, runs in self._states.items():
            if f"branch={branch}&" in url:
                if branch in self._fail:
                    return CommandResult(7, "", "curl: (7) Failed to connect")
                return CommandResult(0, runs, "")
        return CommandResult(0, json.dumps({"workflow_runs": []}), "")


class RecordingAlerts:
    def __init__(self) -> None:
        self.alerts: list[ChainAlert] = []

    def __call__(self, alert: ChainAlert) -> None:
        self.alerts.append(alert)


def _opener(run: WorkflowRun, correlation_ref: str, number: int) -> Mission | None:
    return Mission.create(goal=f"fix (attempt {number})", tenant=platform_tenant())


def _finished_now(attempt: ChainAttempt) -> bool:
    return True  # each attempt finishes between polls, so the scheduler tests see a fresh advance


def _no_sleep(seconds: float) -> None:
    return None


def _monitor(
    runner: RoutingRunner, *, max_attempts: int = 3
) -> tuple[ContinuousMonitor, RecordingAlerts]:
    github = GitHubActions(runner, "o/r", token="t")
    driver = ChainDriver(
        github, AttemptStore(), _opener, is_finished=_finished_now, max_attempts=max_attempts
    )
    alerts = RecordingAlerts()
    monitor = ContinuousMonitor(github, driver, on_alert=alerts, sleep=_no_sleep)
    return monitor, alerts


def test_tick_advances_every_open_pr_once() -> None:
    runner = RoutingRunner(
        _pulls_json((1, "alpha"), (2, "beta")), {"alpha": _GREEN, "beta": _GREEN}
    )
    monitor, alerts = _monitor(runner)
    outcomes = monitor.tick()
    assert [o.status for o in outcomes] == [ChainStatus.GREEN, ChainStatus.GREEN]
    assert runner.pull_calls == 1  # the open PRs were listed once for the pass
    assert alerts.alerts == []


def test_tick_does_nothing_extra_for_pending_or_opened() -> None:
    # beta is still running (PENDING → nothing); alpha is red under the cap (OPENED → the Driver
    # opened the mission, the Worker adds nothing). Neither raises an alert.
    runner = RoutingRunner(
        _pulls_json((1, "alpha"), (2, "beta")), {"alpha": _RED, "beta": _RUNNING}
    )
    monitor, alerts = _monitor(runner)
    outcomes = monitor.tick()
    assert [o.status for o in outcomes] == [ChainStatus.OPENED, ChainStatus.PENDING]
    assert alerts.alerts == []


def test_tick_records_the_alert_when_a_chain_is_exhausted() -> None:
    runner = RoutingRunner(_pulls_json((1, "alpha")), {"alpha": _RED})
    monitor, alerts = _monitor(runner, max_attempts=1)
    first = monitor.tick()  # red, count 0 < 1 → OPENED
    assert first[0].status is ChainStatus.OPENED and alerts.alerts == []
    second = monitor.tick()  # red, count 1 ≥ 1 → EXHAUSTED
    assert second[0].status is ChainStatus.EXHAUSTED
    assert len(alerts.alerts) == 1
    assert alerts.alerts[0].correlation_ref == "pr-1" and alerts.alerts[0].attempts == 1


def test_tick_survives_one_prs_error_and_keeps_going() -> None:
    runner = RoutingRunner(
        _pulls_json((1, "alpha"), (2, "beta")),
        {"alpha": _GREEN, "beta": _GREEN},
        fail_branches=frozenset({"alpha"}),
    )
    monitor, _alerts = _monitor(runner)
    outcomes = monitor.tick()  # alpha's query fails → logged and skipped; beta still advances
    assert [o.status for o in outcomes] == [ChainStatus.GREEN]


class _StopMonitor(Exception):
    """Breaks the otherwise-infinite run_forever loop from the injected sleep, for the test."""


def test_run_forever_ticks_then_sleeps_until_stopped() -> None:
    runner = RoutingRunner(_pulls_json(), {})  # no open PRs → each tick is a no-op
    github = GitHubActions(runner, "o/r", token="t")
    driver = ChainDriver(github, AttemptStore(), _opener, is_finished=_finished_now)
    sleeps: list[float] = []

    def stopping_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 3:
            raise _StopMonitor

    monitor = ContinuousMonitor(github, driver, poll_seconds=30.0, sleep=stopping_sleep)
    with pytest.raises(_StopMonitor):
        monitor.run_forever()
    assert sleeps == [30.0, 30.0, 30.0]  # looped three times at the polling cadence
    assert runner.pull_calls == 3  # tick really ran each iteration
