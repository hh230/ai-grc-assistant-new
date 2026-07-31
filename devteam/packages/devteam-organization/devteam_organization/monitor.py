"""The organization's always-on Worker — continuous operation (§11; ADR 0061 daemon shape).

A pure scheduler, mirroring the engineering squad's ``ContinuousMonitor``: it holds no policy. Each
pass (``tick``): drain any pending mission intents and run them through the organization, take one
Supervisor pass (health / stall detection / recovery), and beat the Supervisor's heartbeat as a real
observed mission. ``run_forever`` is the loop — tick, sleep, repeat — surviving any single pass's
error so an all-day Worker never dies.

Real activity only: with no pending intents the Worker still supervises and heartbeats over real
runtime facts. It fabricates nothing. It writes the SAME journal the Dashboard reads, so the whole
organization — every agent, every mission, every decision — appears in the existing Dashboard live.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from devteam_ci import PackageResult, run_package
from devteam_github import GitHubActions
from devteam_observability import (
    JOURNAL_FILENAME,
    DevTeamObservability,
    JournalingObserver,
)
from devteam_tools import SubprocessCommandRunner
from dotenv import load_dotenv
from mission_engine.mission import Mission

from devteam_organization.connectors import ConnectorConfig, ConnectorRegistry, build_registry
from devteam_organization.connectors.snapshot import write_connectors_snapshot
from devteam_organization.lifecycle_host import (
    OrganizationLifecycle,
    build_organization_lifecycle,
    recover_lifecycle,
    write_lifecycle_snapshot,
)
from devteam_organization.operations_projection import write_operations_snapshot
from devteam_organization.runtime import OrganizationRuntime
from devteam_organization.supervisor import SupervisionOutcome, Supervisor, engine_recovery

_LOG = logging.getLogger("devteam.organization.monitor")

# The two permanent workers the Supervisor/Runtime-Health jobs watch (both feed the one journal).
_ORG_LABEL = "com.rasheed.devteam-organization"
_SQUAD_LABEL = "com.rasheed.devteam-monitor"

# The runtime journal the Worker writes and the Dashboard reads — the SAME file the engineering
# squad's monitor and the dashboard already share (one source of truth, outside the repo).
_DEFAULT_JOURNAL = Path.home() / "Library" / "Logs" / "devteam-monitor" / JOURNAL_FILENAME

# Pending mission goals to run this pass. Injected; the default is none (the Worker supervises and
# heartbeats until real intents arrive). A file/queue realization plugs in here with no code change.
IntentSource = Callable[[], Sequence[str]]


def _no_intents() -> Sequence[str]:
    return ()


class QueueIntentSource:
    """A drain-once intent source: it yields its pending goals exactly once, then is empty (so the
    Worker runs each submitted mission a single time, never re-running it every pass). Real intents
    are appended by an operator/CLI via ``submit`` — never fabricated by the Worker itself."""

    def __init__(self, goals: Sequence[str] = ()) -> None:
        self._pending: list[str] = list(goals)

    def submit(self, goal: str) -> None:
        self._pending.append(goal)

    def __call__(self) -> Sequence[str]:
        drained, self._pending = self._pending, []
        return drained


@dataclass(frozen=True)
class TickOutcome:
    """What one pass did — missions run, the supervision result, the heartbeat mission, and whether
    the lifecycle synced this tick."""

    missions: tuple[Mission, ...]
    supervision: SupervisionOutcome
    heartbeat: Mission | None
    synced: bool = False


class OrganizationMonitor:
    """Always-on Worker over the organization. Inject the runtime, the Supervisor, the intent source
    (what missions to run), the poll cadence, and ``sleep`` (so tests drive the loop, no wait)."""

    def __init__(
        self,
        runtime: OrganizationRuntime,
        supervisor: Supervisor,
        *,
        intents: IntentSource = _no_intents,
        poll_seconds: float = 60.0,
        heartbeat_every: int = 1,
        lifecycle: OrganizationLifecycle | None = None,
        after_tick: Callable[[], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._runtime = runtime
        self._supervisor = supervisor
        self._intents = intents
        self._poll_seconds = poll_seconds
        self._lifecycle = lifecycle
        # Called after each tick (e.g. to write the connectors snapshot the Dashboard reads).
        self._after_tick = after_tick
        # The Supervisor SUPERVISES every tick (read-only, no journal growth); it records an
        # OBSERVABLE heartbeat mission every ``heartbeat_every`` ticks. Decoupling the two keeps a
        # 24/7 service's append-only journal bounded while still checking every agent each poll.
        self._heartbeat_every = max(1, heartbeat_every)
        self._sleep = sleep
        self._tick_count = 0

    def tick(self) -> TickOutcome:
        """One pass: run pending mission intents, supervise (every tick), and record the observable
        heartbeat mission on the heartbeat cadence. One mission's failure is logged and skipped — it
        never aborts the pass (an all-day Worker survives a bad intent)."""
        self._tick_count += 1
        missions: list[Mission] = []
        for goal in self._intents():
            try:
                mission = self._runtime.run_mission(goal)
            except Exception:
                _LOG.exception("organization mission failed for goal %r", goal)
                continue
            _LOG.info("mission %s (%s): %s", mission.id, goal, mission.status.value)
            missions.append(mission)

        # Continuous monitoring: read every agent's health from the live view, every tick.
        supervision = self._supervisor.supervise()
        if not supervision.healthy:
            _LOG.warning("supervisor: %s", supervision.report.summary)

        # Observable pulse: a real health-check mission on the first tick and every Nth after, so
        # the Supervisor is visibly alive in the Dashboard without flooding the journal each poll.
        heartbeat: Mission | None = None
        if (self._tick_count - 1) % self._heartbeat_every == 0:
            try:
                heartbeat = self._supervisor.heartbeat()
            except Exception:
                _LOG.exception("supervisor heartbeat failed")

        # The single operational path: the lifecycle syncs each tick — connectors emit signals,
        # adapter events notify, the coordinator reconciles. The LifecycleCoordinator is the sole
        # owner of every problem's state; the daemon only hosts it (no lifecycle logic here).
        synced = False
        if self._lifecycle is not None:
            try:
                self._lifecycle.sync()
                synced = True
            except Exception:
                _LOG.exception("lifecycle sync failed")

        # Publish read-only projections: connector state + the lifecycle snapshot (Dashboard reads).
        if self._after_tick is not None:
            try:
                self._after_tick()
            except Exception:
                _LOG.exception("after-tick hook failed")

        return TickOutcome(tuple(missions), supervision, heartbeat, synced)

    def run_forever(self) -> None:
        """Operate continuously: tick, sleep, repeat — forever. A whole failed pass is logged and
        the loop continues; the injected ``sleep`` paces the poll."""
        while True:
            try:
                self.tick()
            except Exception:
                _LOG.exception("organization tick failed; continuing")
            self._sleep(self._poll_seconds)


def bounded_org_suite_runner(
    repo_root: Path | str, *, timeout: float = 300.0
) -> Callable[[], Sequence[PackageResult]]:
    """The organization's default QA runner: a REAL, bounded self-check — it runs the
    devteam-organization package's own suite via ``uv`` (one package, real result). Honest and fast
    enough for a live Worker; a composition wanting the full platform gate injects a broader runner.
    """
    package = Path(repo_root) / "devteam" / "packages" / "devteam-organization"

    def run() -> Sequence[PackageResult]:
        return [run_package(package, timeout=timeout)]

    return run


def build_connector_registry(
    runtime: OrganizationRuntime, *, config_path: str | None, repo_root: str
) -> ConnectorRegistry:
    """Build the read-only connector registry from the config: the source of evidence the lifecycle
    reads (emission + verification). The registry watches the two service workers + the live view.
    Empty config ⇒ Unavailable connectors ⇒ no problems (no fabrication). It observes; it never
    mutates a problem's state — that is the LifecycleCoordinator's alone."""
    config = ConnectorConfig.load(config_path)
    # The runtime connector always watches the two permanent workers, even if the file omits them.
    workers = tuple(dict.fromkeys((_ORG_LABEL, _SQUAD_LABEL, *config.runtime_workers)))
    config = replace(config, runtime_workers=workers)
    github: GitHubActions | None = None
    if config.github_repo:
        github = GitHubActions(
            SubprocessCommandRunner(), config.github_repo, token=os.environ.get("GITHUB_TOKEN")
        )
    return build_registry(
        config, view_provider=lambda: runtime.view, github=github, repo_root=repo_root
    )


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - loops forever
    """Launch the organization Worker. Writes the runtime journal the Dashboard observes; supervises
    and heartbeats; hosts the mission Lifecycle every tick (the single operational path); runs any
    ``--goal`` missions once at startup. Deployment (service/cron/launchd) wraps this — not it."""
    parser = argparse.ArgumentParser(description="Run the AI Organization continuously.")
    parser.add_argument("--repo-root", default=".", help="repo root (QA self-check + .env)")
    parser.add_argument("--poll-seconds", type=float, default=60.0, help="seconds between passes")
    parser.add_argument(
        "--heartbeat-every", type=int, default=1, help="record a heartbeat mission every Nth tick"
    )
    parser.add_argument("--stall-after-s", type=float, default=900.0, help="stall threshold")
    parser.add_argument(
        "--goal", action="append", default=[], help="an organization mission to run (repeatable)"
    )
    parser.add_argument("--once", action="store_true", help="run one pass and exit")
    parser.add_argument(
        "--journal", default=str(_DEFAULT_JOURNAL), help="runtime journal the Dashboard observes"
    )
    parser.add_argument(
        "--no-journal", action="store_true", help="disable the runtime journal (no observability)"
    )
    parser.add_argument(
        "--config", default=None, help="path to the connectors/jobs config (YAML or JSON)"
    )
    parser.add_argument("--no-jobs", action="store_true", help="disable the lifecycle (connectors)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv(Path(args.repo_root) / ".env")

    observability: DevTeamObservability | None = None
    if not args.no_journal:
        observability = DevTeamObservability(downstreams=[JournalingObserver(args.journal)])
        _LOG.info("observability on — writing runtime journal to %s", args.journal)

    runtime = OrganizationRuntime(
        bounded_org_suite_runner(args.repo_root),
        observability=observability,
        stall_after_s=args.stall_after_s,
    )
    supervisor = Supervisor(
        runtime, recover=engine_recovery(runtime), stall_after_s=args.stall_after_s
    )
    lifecycle: OrganizationLifecycle | None = None
    after_tick: Callable[[], None] | None = None
    if not args.no_jobs:
        journal_dir = Path(args.journal).parent
        registry = build_connector_registry(
            runtime, config_path=args.config, repo_root=args.repo_root
        )
        org_lifecycle = build_organization_lifecycle(runtime, registry)
        lifecycle = org_lifecycle
        connectors_path = journal_dir / "connectors.json"
        lifecycle_path = journal_dir / "lifecycle.json"
        operations_path = journal_dir / "operations.json"
        recovered = recover_lifecycle(org_lifecycle.composition, lifecycle_path)

        def after_tick() -> None:
            write_connectors_snapshot(registry.states(), connectors_path)
            write_lifecycle_snapshot(org_lifecycle.composition, lifecycle_path)
            # The single artifact the Viewer reads (Core -> Projection -> Viewer).
            write_operations_snapshot(org_lifecycle.snapshot(now=time.time()), operations_path)

        after_tick()  # publish the seeded connector roster + the recovered lifecycle immediately
        _LOG.info(
            "lifecycle on — %d connector(s), %d problem(s) recovered",
            len(registry.states()),
            recovered,
        )

    intents = QueueIntentSource(args.goal)  # drains once — each --goal mission runs a single time
    monitor = OrganizationMonitor(
        runtime,
        supervisor,
        intents=intents,
        poll_seconds=args.poll_seconds,
        heartbeat_every=args.heartbeat_every,
        lifecycle=lifecycle,
        after_tick=after_tick,
    )

    if args.once:
        outcome = monitor.tick()
        _LOG.info(
            "one pass: %d mission(s), health=%s",
            len(outcome.missions),
            "healthy" if outcome.supervision.healthy else outcome.supervision.report.summary,
        )
        return 0

    _LOG.info("AI Organization operating; polling every %.0fs", args.poll_seconds)
    monitor.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
