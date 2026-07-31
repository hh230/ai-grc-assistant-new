"""ChainDriver — the continue-until-green policy over the frozen Core + the devteam-chain model.

The retry loop ADR 0061 calls for, built ON TOP of the attempt model (devteam-chain). The Mission
Engine, the Core, and the correlation model are untouched. One decision step, ``advance``: watch a
branch's CI (GitHubActions.latest_run_for_branch) and, on red, advance the correlated chain — open
the next fix-it mission (attempt N+1, via the injected opener) until CI is green or max_attempts is
reached, at which point it raises a ChainAlert (human intervention) INSTEAD of another mission.

The Driver owns ALL policy: read the history, compute the next attempt, compare max_attempts, raise
the alert, open when needed. The AttemptStore is data only; the engine is execution only. Opening a
mission is injected, so the policy is deterministic and testable without the network or the DB.
``build_chain_driver`` wires the real opener (GitHub logs -> analysis -> Developer -> gate).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from devteam_agents import AnalysisProposer
from devteam_analysis import FailureAnalyzer
from devteam_chain import AttemptStore, ChainAlert, ChainAttempt
from devteam_contracts import platform_tenant
from devteam_github import GitHubActions, WorkflowRun
from devteam_observability import DevTeamObservability
from devteam_tools import CommandRunner
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.lifecycle import is_terminal
from mission_engine.mission import Mission
from mission_engine.ports import MissionStorePort

from devteam_runtime.fix_it_runtime import FixItRuntime
from devteam_runtime.github_ci import analyze_run_failure

# How the Driver opens the next fix-it mission for a failed run (correlation_ref + attempt number).
OpenMission = Callable[[WorkflowRun, str, int], Mission | None]

# Whether a recorded attempt's mission has finished (terminal). Read from the AttemptStore's own
# record — the single source of truth — via its mission_id, never Driver state (injected, pure).
IsFinished = Callable[[ChainAttempt], bool]


class ChainStatus(str, Enum):
    """The verdict of one ChainDriver.advance step."""

    GREEN = "green"  # CI passed — the chain is resolved; stop.
    PENDING = "pending"  # CI still running, or no run yet — keep watching.
    OPENED = "opened"  # CI red, under the cap — opened the next fix-it mission.
    EXHAUSTED = "exhausted"  # CI red at the cap — raised a ChainAlert, not a mission.


@dataclass(frozen=True)
class ChainOutcome:
    """What one advance step decided: the status, the watched run, and — per status — the new
    attempt and its mission, or the alert (``mission`` is None if no failing step was found)."""

    status: ChainStatus
    run: WorkflowRun | None = None
    attempt: ChainAttempt | None = None
    mission: Mission | None = None
    alert: ChainAlert | None = None


class ChainDriver:
    """Continue-until-green policy: watch a branch's CI, and on red advance the correlated chain
    until green or exhausted. AT MOST ONE in-flight attempt per chain — while the latest attempt's
    mission is unfinished, ``advance`` returns PENDING no matter how long CI stays red; only a
    *finished* attempt (approved, rejected, cancelled, failed) lets the next one open. So the chain
    tracks the attempt's STATE, not the poll count or run id — like an engineer, not a stopwatch.

    STATELESS: the AttemptStore is the single source of truth. The Driver reads the latest attempt
    (and, via its mission_id, that mission's live status) from the store each pass and holds NOTHING
    itself — a Worker restart changes nothing. Opening a mission and reading whether an attempt
    finished are injected. ``advance`` is one step — a loop calls it until GREEN or EXHAUSTED."""

    def __init__(
        self,
        github: GitHubActions,
        store: AttemptStore,
        open_mission: OpenMission,
        *,
        is_finished: IsFinished,
        max_attempts: int = 3,
    ) -> None:
        self._github = github
        self._store = store
        self._open_mission = open_mission
        self._is_finished = is_finished
        self._max_attempts = max_attempts

    def advance(self, correlation_ref: str, branch: str) -> ChainOutcome:
        """One continue-until-green step. Watches ``branch``: GREEN if CI passed, PENDING if it is
        still running OR the latest attempt is still in flight, else advances the chain — EXHAUSTED
        (a ChainAlert) once max_attempts is reached, else OPENED: opens the next fix-it mission."""
        run = self._github.latest_run_for_branch(branch)
        if run is None or run.is_pending:
            return ChainOutcome(ChainStatus.PENDING, run=run)
        if run.is_success:
            return ChainOutcome(ChainStatus.GREEN, run=run)
        # CI is red. Read the chain's state from the store (the SSoT): one in-flight attempt per
        # chain — while the latest attempt is unfinished, wait; a finished one lets the next open.
        latest = self._store.latest(correlation_ref)
        if latest is not None and not self._is_finished(latest):
            return ChainOutcome(ChainStatus.PENDING, run=run)
        if self._store.count(correlation_ref) >= self._max_attempts:
            alert = self._alert(correlation_ref, self._store.count(correlation_ref))
            return ChainOutcome(ChainStatus.EXHAUSTED, run=run, alert=alert)
        number = latest.attempt_number + 1 if latest is not None else 1
        mission = self._open_mission(run, correlation_ref, number)
        if mission is None:
            return ChainOutcome(ChainStatus.PENDING, run=run)  # nothing to open this pass
        attempt = ChainAttempt(correlation_ref, number, mission_id=mission.id)
        self._store.record(attempt)
        return ChainOutcome(ChainStatus.OPENED, run=run, attempt=attempt, mission=mission)

    def _alert(self, correlation_ref: str, attempts: int) -> ChainAlert:
        return ChainAlert(
            correlation_ref=correlation_ref,
            attempts=attempts,
            reason=(
                f"CI still failing after {attempts} attempt(s) "
                f"(max_attempts={self._max_attempts}); needs human intervention"
            ),
        )


def build_chain_driver(
    github: GitHubActions,
    *,
    repo_root: str | Path,
    git_runner: CommandRunner,
    store: AttemptStore | None = None,
    mission_store: MissionStorePort | None = None,
    analyzers: Sequence[FailureAnalyzer] | None = None,
    max_attempts: int = 3,
    observability: DevTeamObservability | None = None,
) -> ChainDriver:
    """Wire a production ChainDriver. On red, it opens the next attempt by downloading the failed
    run's real logs, normalizing them (the analyzers), and running the Developer -> gate flow — the
    same wiring the first failure uses — tagging the mission goal with the correlation_ref + attempt
    (how a Core mission 'carries' its place in the chain).

    All the chain's attempts share ONE mission store, so ``is_finished`` reads each attempt's LIVE
    status (terminal = finished). Pass ``mission_store`` to share it with the approval flow that
    resolves the gate — until an attempt finishes there, the chain correctly stays PENDING.
    Pass ``observability`` to make every fix-it mission emit runtime facts (e.g. to a journal the
    Dashboard reads); omitting it leaves the chain byte-for-byte as before."""
    missions = mission_store if mission_store is not None else InMemoryMissionStore()

    def _open(run: WorkflowRun, correlation_ref: str, number: int) -> Mission | None:
        result = analyze_run_failure(github, run.id, repo_root=repo_root, analyzers=analyzers)
        if result is None:
            return None
        _step, analysis = result
        runtime = FixItRuntime(
            propose=AnalysisProposer(analysis, repo_root),
            runner=git_runner,
            repo_root=repo_root,
            store=missions,
            observability=observability,
        )
        issue = f"{analysis.summary} [{correlation_ref}: attempt {number}]"
        return runtime.open_fix_it(issue)

    def _is_finished(attempt: ChainAttempt) -> bool:
        # Re-read the attempt's mission from the shared store (all dev-team missions are platform-
        # tenant; get() scopes by tenant_id only). Terminal — or gone — means the attempt finished.
        current = missions.get(attempt.mission_id, platform_tenant())
        return current is None or is_terminal(current.status)

    return ChainDriver(
        github, store or AttemptStore(), _open, is_finished=_is_finished, max_attempts=max_attempts
    )
