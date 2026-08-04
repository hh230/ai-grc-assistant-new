"""The team run — what a release gate actually executes.

Order matters and encodes the QA workflow: explore the space, attack it, verify what came back,
then replay everything that ever failed. The Reporter runs last because it is the only role that
reads every other role's output.
"""

from __future__ import annotations

from dataclasses import dataclass

from devteam_harness.agents import (
    breaker,
    explorer,
    pilot,
    regression,
    saboteur,
    sentry,
    verifier,
)
from devteam_harness.agents.base import AgentReport
from devteam_harness.agents.reporter import Report, compile_report
from devteam_harness.results import ResultStore
from devteam_harness.surfaces.browser import BrowserSurface


@dataclass
class TeamOutcome:
    report: Report
    reports: list[AgentReport]

    @property
    def ok(self) -> bool:
        return self.report.ok


def run_team(
    *,
    count: int = 200,
    start_seed: int = 0,
    breaker_samples: int = 25,
    store: ResultStore | None = None,
    previous_run_id: int | None = None,
    browser: bool = False,
    http: bool = False,
) -> TeamOutcome:
    """Run the whole team once.

    `http` and `browser` are opt-in because both need a RUNNING app, and the two gates this
    harness serves are different. Every PR runs the in-process gate: deterministic, needs nothing,
    and detects a regression in the product's own logic. A pre-release run adds `--http --browser`
    against a deployed environment. Making them default would put a permanent "the app was not
    running" gap into every CI run, and a gate that is always incomplete is a gate nobody reads.

    Asking for a surface and not getting it is still REPORTED — the flag declares intent, it does
    not lower the bar.

    `browser` is opt-in because Pilot drives a real Chromium over every page in both locales and
    both viewports — minutes, not seconds, against a dev server. A release gate should turn it on;
    an inner-loop run generally should not. When it is off, no Pilot report is produced at all,
    so the summary cannot imply browser coverage that never happened.

    `store`/`previous_run_id` are how Regression gets its work: the seeds that failed in an
    earlier recorded run. Without them the team still runs — it simply has no history to replay
    yet, which is the correct behaviour on a first ever run rather than an error.
    """
    reports: list[AgentReport] = []

    explorer_report, _coverage = explorer.run(count=count, start_seed=start_seed)
    reports.append(explorer_report)

    breaker_aggregate = AgentReport(agent=breaker.AGENT)
    for offset in range(breaker_samples):
        single = breaker.run(start_seed + offset)
        breaker_aggregate.findings.extend(single.findings)
        for key, value in single.stats.items():
            breaker_aggregate.bump(key, value)
    reports.append(breaker_aggregate)

    reports.append(verifier.run(count=count, start_seed=start_seed))

    # Sentry needs a running app. It reports its own absence as a finding rather than skipping,
    # so a gate can refuse to treat "the app was down" as a pass.
    if http:
        reports.append(sentry.run())
        # The Breaker's live arm: concurrency, double submits, hostile payloads at the API edge.
        reports.append(saboteur.run())

    if browser:
        reports.append(pilot.run())
        # Rapid clicks and multiple tabs — races that only exist once there is a real browser.
        reports.append(saboteur.run_browser(BrowserSurface()))

    if store is not None and previous_run_id is not None:
        regression_report, _outcome = regression.from_store(store, previous_run_id)
        reports.append(regression_report)

    return TeamOutcome(report=compile_report(reports), reports=reports)
