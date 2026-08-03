"""Regression — re-runs everything that ever failed, after every change.

This is the agent that makes the harness a *release gate* rather than a fuzzer: it does not
sample randomly, it replays the exact seeds that failed before. Two outcomes matter and both are
reported, because only one of them is usually noticed:

  - still failing  -> the bug is not fixed
  - now passing    -> the bug IS fixed, and this seed should become a permanent guard

Reporting fixes is not decoration. A seed that silently starts passing is a regression test
nobody wrote; surfacing it is how a one-off finding becomes lasting coverage.
"""

from __future__ import annotations

from dataclasses import dataclass

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.campaign import check_scenario
from devteam_harness.results import ResultStore

AGENT = "regression"


@dataclass(frozen=True)
class RegressionOutcome:
    still_failing: list[int]
    now_passing: list[int]


def run(seeds: list[int]) -> tuple[AgentReport, RegressionOutcome]:
    """Replay known-bad seeds and classify what happened."""
    report = AgentReport(agent=AGENT)
    still_failing: list[int] = []
    now_passing: list[int] = []

    for seed in seeds:
        report.bump("replayed")
        checked = check_scenario(seed)
        if checked.ok:
            now_passing.append(seed)
            report.bump("now_passing")
        else:
            still_failing.append(seed)
            report.bump("still_failing")
            worst = max(
                (v.name for v in checked.violations),
                default=checked.result.error_type or "unknown",
            )
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.INVARIANT,
                    kind=f"still_failing:{worst}",
                    detail=f"seed {seed} failed before and still fails",
                    reproduce=f"python -m devteam_harness --seed {seed}",
                    seed=seed,
                )
            )

    return report, RegressionOutcome(still_failing=still_failing, now_passing=now_passing)


def from_store(store: ResultStore, run_id: int) -> tuple[AgentReport, RegressionOutcome]:
    """Replay every seed that failed in a previous recorded run."""
    return run(store.failing_seeds(run_id))
