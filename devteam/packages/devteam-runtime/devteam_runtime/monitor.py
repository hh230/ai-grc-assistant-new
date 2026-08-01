"""ContinuousMonitor — the dev team's always-on Worker (ADR 0061).

The daemon that makes "watch the project all day, and if CI fails fix the code" real, not a manual
entry point. It is a PURE SCHEDULER: it holds NO policy. Every decision lives downstream in the
ChainDriver (which in turn owns GitHubActions, the FailureAnalyzers, the Developer, and the Mission
Engine). The Worker knows nothing about GitHub logs, analysis, or diffs.

Each pass (``tick``): list open PRs, call ``ChainDriver.advance`` per PR. React minimally to the
outcome — GREEN / PENDING / OPENED need nothing (the Driver already did the work); EXHAUSTED
only records the alert. ``run_forever`` is the loop: tick, sleep, repeat. No threads, no async, no
queue — a plain while+sleep, so it stays trivially testable; the deployment shape (service / cron /
k8s) is a later decision, taken only once this Worker runs on its own.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from devteam_chain import ChainAlert
from devteam_github import GitHubActions
from devteam_observability import JOURNAL_FILENAME, DevTeamObservability, JournalingObserver
from devteam_tools import SubprocessCommandRunner
from dotenv import load_dotenv

from devteam_runtime.chain_driver import (
    ChainDriver,
    ChainOutcome,
    ChainStatus,
    build_chain_driver,
)

_LOG = logging.getLogger("devteam.monitor")

# The runtime journal the Worker writes so a separate Dashboard process can observe the agents. It
# lives OUTSIDE the repo, alongside the monitor logs (the same directory the LaunchAgent logs to),
# so nothing in the working tree changes. The FILENAME is shared with the dashboard reader via
# ``JOURNAL_FILENAME`` (one source of truth). Override with --journal; disable with --no-journal.
_DEFAULT_JOURNAL = Path.home() / "Library" / "Logs" / "devteam-monitor" / JOURNAL_FILENAME


def _log_alert(alert: ChainAlert) -> None:
    _LOG.warning(
        "chain %s EXHAUSTED after %d attempt(s): %s",
        alert.correlation_ref,
        alert.attempts,
        alert.reason,
    )


class ContinuousMonitor:
    """Always-on Worker over the ChainDriver: watch every open PR and advance its chain, forever. A
    pure scheduler — no policy. Inject ``poll_seconds`` (cadence), ``on_alert`` (what to do with an
    EXHAUSTED chain — default logs it), and ``sleep`` (so tests drive the loop with no wait)."""

    def __init__(
        self,
        github: GitHubActions,
        driver: ChainDriver,
        *,
        poll_seconds: float = 60.0,
        on_alert: Callable[[ChainAlert], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._github = github
        self._driver = driver
        self._poll_seconds = poll_seconds
        self._on_alert = on_alert or _log_alert
        self._sleep = sleep

    def tick(self) -> list[ChainOutcome]:
        """One monitoring pass: advance every open PR's chain once, returning the outcomes (for
        observability / tests). EXHAUSTED records the alert; every other status is left to the
        Driver, which already acted. One PR's failure is logged and skipped — it never aborts."""
        pulls = self._github.open_pull_requests()
        _LOG.info("monitoring %d open PR(s)", len(pulls))
        outcomes: list[ChainOutcome] = []
        for pull in pulls:
            try:
                outcome = self._driver.advance(pull.correlation_ref, pull.head_branch)
            except Exception:
                # A pure scheduler must survive one PR's error (a transient GitHub/network blip) and
                # keep watching the rest — an all-day Worker cannot die on a single bad PR.
                _LOG.exception("advance failed for PR %s (%s)", pull.number, pull.head_branch)
                continue
            if outcome.status is ChainStatus.EXHAUSTED and outcome.alert is not None:
                self._on_alert(outcome.alert)
            elif outcome.status is ChainStatus.OPENED and outcome.mission is not None:
                # Log the opened attempt + its outcome so the run records the operating metrics: a
                # mission that is awaiting_approval carries a patch (a human approves it by this id
                # via the ApprovalGateway); a cancelled one means the Developer produced no patch
                # (human intervention required). The Worker never self-approves.
                attempt = outcome.attempt.attempt_number if outcome.attempt is not None else 0
                _LOG.info(
                    "PR %s: opened mission %s (attempt %d) — %s",
                    pull.number,
                    outcome.mission.id,
                    attempt,
                    outcome.mission.status.value,
                )
            elif outcome.status is ChainStatus.GREEN:
                _LOG.info("PR %s: CI is green — chain resolved", pull.number)
            outcomes.append(outcome)
        return outcomes

    def run_forever(self) -> None:
        """Watch the project all day: tick, sleep, repeat — forever. A whole failed pass is logged,
        and the loop continues (the daemon does not die); the injected ``sleep`` paces the poll."""
        while True:
            try:
                self.tick()
            except Exception:
                # Backstop for a pass-level failure (e.g. listing the PRs itself failed): log, then
                # sleep and try again next cycle rather than crashing the daemon.
                _LOG.exception("monitor tick failed; continuing")
            self._sleep(self._poll_seconds)


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - loops forever
    """Launch the Worker against a real repository: watch its open PRs and advance each chain,
    forever. Local-dev token injection reads a repo-root .env (a no-op in CI/prod, where the token
    is already in the environment). This is the process; the deployment shape (service/cron/k8s)
    wraps it later — it is not it."""
    parser = argparse.ArgumentParser(description="Continuously watch a repo's PRs and fix red CI.")
    parser.add_argument("--repo", required=True, help="owner/name of the GitHub repo to watch")
    parser.add_argument("--repo-root", default=".", help="working tree the fixes target")
    parser.add_argument("--poll-seconds", type=float, default=60.0, help="seconds between passes")
    parser.add_argument("--max-attempts", type=int, default=3, help="fix attempts before alerting")
    parser.add_argument(
        "--journal", default=str(_DEFAULT_JOURNAL), help="runtime journal the Dashboard observes"
    )
    parser.add_argument(
        "--no-journal", action="store_true", help="disable the runtime journal (no observability)"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv(Path(args.repo_root) / ".env")
    token = os.environ.get("GITHUB_TOKEN")
    github = GitHubActions(SubprocessCommandRunner(), args.repo, token=token)

    # Observability is on by default: the Worker writes a runtime journal a separate Dashboard
    # process reads. It only appends a file — it never changes what a mission does — and passing
    # nothing leaves the chain unobserved (backward-compatible).
    observability: DevTeamObservability | None = None
    if not args.no_journal:
        observability = DevTeamObservability(downstreams=[JournalingObserver(args.journal)])
        _LOG.info("observability on — writing runtime journal to %s", args.journal)

    driver = build_chain_driver(
        github,
        repo_root=args.repo_root,
        git_runner=SubprocessCommandRunner(),
        max_attempts=args.max_attempts,
        observability=observability,
    )
    monitor = ContinuousMonitor(github, driver, poll_seconds=args.poll_seconds)
    _LOG.info("watching %s every %.0fs", args.repo, args.poll_seconds)
    monitor.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
