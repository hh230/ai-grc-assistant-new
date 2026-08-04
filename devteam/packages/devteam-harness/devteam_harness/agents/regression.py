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

from devteam_harness.agents.base import AgentReport, Finding, Severity, findings_for_seed
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
        findings, ok = findings_for_seed(seed, AGENT)
        if ok:
            now_passing.append(seed)
            report.bump("now_passing")
            continue
        still_failing.append(seed)
        report.bump("still_failing")
        # Re-labelled, not re-derived: the finding is the same one the Verifier would produce;
        # what Regression adds is the knowledge that it ALSO failed last time.
        worst = max((f.kind for f in findings), default="unknown")
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
