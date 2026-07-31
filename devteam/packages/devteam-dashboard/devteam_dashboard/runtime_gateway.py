"""RuntimeGateway — the ONE seam between the dashboard and the runtime.

Everything the dashboard does against the runtime goes through here, and here does nothing but
COMPOSE the existing public services — exactly the composition ``operate.py`` uses (ADR 0061):

  observe    → open_pull_requests / latest_run_for_branch   (read-only, live CI)
  materialize→ analyze_run_failure → FixItRuntime.open_fix_it   (re-derive the gated mission)
  approve    → ApprovalGateway.approve(mission_id)   (the EXISTING gate → land)
  reject     → ApprovalGateway.reject(mission_id)    (the EXISTING gate → cancel)

No decision logic lives here. The daemon keeps its missions in its own process memory (unreachable
across processes), so — like ``operate.py`` — the dashboard re-derives a PR's gated mission into its
OWN in-memory store on demand; the analyzers + AnalysisProposer are deterministic (LLM-free),
the diff shown is the diff that lands. View and approve act on the SAME materialization: one store,
held for the process, so ``approve(mission_id)`` finds exactly what the operator reviewed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from devteam_agents import AnalysisProposer
from devteam_github import GitHubActions, GitHubError, PullRequest, WorkflowRun
from devteam_runtime import ApprovalGateway, FixItRuntime
from devteam_runtime.github_ci import analyze_run_failure
from devteam_tools import CommandRunner, SubprocessCommandRunner, extract_diff
from dotenv import load_dotenv
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.lifecycle import MissionStatus
from mission_engine.mission import Mission
from mission_engine.ports import MissionStorePort

from devteam_dashboard.actions_log import ActionsLog
from devteam_dashboard.config import DashboardConfig

_PR_URL_RE = re.compile(r"https://\S+?/pull/\d+")


@dataclass(frozen=True)
class PrRow:
    """One open PR as the Open Missions table sees it (the live actionable set). ``actionable`` is
    True when the latest CI run failed — i.e. the daemon would open a gated fix-it mission."""

    pr_number: int
    repo: str
    head_branch: str
    title: str
    html_url: str
    ci_status: str  # failing | pending | green | no_run | unknown
    actionable: bool


@dataclass(frozen=True)
class FindingView:
    file: str
    line: int
    code: str
    message: str


@dataclass
class MissionView:
    """A PR's re-derived gated mission for the Details page. ``state`` says what's actionable:
    ``awaiting_approval`` (a diff to review + approve/reject), ``no_patch`` (Developer declined —
    nothing to approve), or an observational state (``green``/``pending``/``no_run``/``error``)."""

    state: str
    pr_number: int
    repo: str
    head_branch: str = ""
    html_url: str = ""
    mission_id: str | None = None
    mission_status: str | None = None
    category: str | None = None
    confidence: float | None = None
    summary: str | None = None
    findings: list[FindingView] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    diff: str | None = None
    failing_job: str | None = None
    failing_step: str | None = None
    approval_reason: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class DecisionResult:
    """The outcome of an approve/reject the dashboard performed via the existing ApprovalGateway."""

    action: str  # approved | rejected
    mission_id: str
    status: str  # the mission's resulting status (completed | cancelled)
    pr_number: int | None
    pr_url: str | None
    output: str


class RuntimeGateway:
    """Composes the existing runtime services for the dashboard. Holds ONE mission store for the
    process so a materialized mission stays approvable. Build via ``build(config)`` in production;
    inject collaborators directly in tests (a fake GitHub + a fake git runner, no network)."""

    def __init__(
        self,
        *,
        github: GitHubActions,
        store: MissionStorePort,
        git_runner: CommandRunner,
        repo_root: Path | str,
        repo: str,
        actions_log: ActionsLog | None = None,
    ) -> None:
        self._github = github
        self._store = store
        self._git = git_runner
        self._repo_root = repo_root
        self._repo = repo
        self._actions = actions_log

    @classmethod
    def build(cls, config: DashboardConfig) -> RuntimeGateway:
        """Production wiring, identical to operate.py: load the repo-root .env for GITHUB_TOKEN, one
        SubprocessCommandRunner for both curl (GitHub) and git/gh (landing), one in-memory store."""
        load_dotenv(config.repo_root / ".env")
        git = SubprocessCommandRunner()
        github = GitHubActions(git, config.repo, token=os.environ.get("GITHUB_TOKEN"))
        return cls(
            github=github,
            store=InMemoryMissionStore(),
            git_runner=git,
            repo_root=config.repo_root,
            repo=config.repo,
            actions_log=ActionsLog(config.actions_log_path),
        )

    # --- observe (read-only) ----------------------------------------------------------------

    def open_prs(self) -> list[PrRow]:
        """The live actionable set: every open PR annotated with its latest CI verdict. May raise
        GitHubError (network/auth) — the caller decides how to degrade."""
        rows: list[PrRow] = []
        for pull in self._github.open_pull_requests():
            run = self._safe_latest_run(pull.head_branch)
            rows.append(
                PrRow(
                    pr_number=pull.number,
                    repo=self._repo,
                    head_branch=pull.head_branch,
                    title=pull.title,
                    html_url=pull.html_url,
                    ci_status=_ci_status(run),
                    actionable=run is not None and run.is_failure,
                )
            )
        return rows

    def github_ok(self) -> tuple[bool, str]:
        """A cheap connectivity probe for the Settings/health signal — one recent run."""
        try:
            self._github.list_runs(per_page=1)
        except GitHubError as exc:
            return False, str(exc)
        return True, "ok"

    # --- materialize (re-derive a PR's gated mission, read-only up to the gate) --------------

    def materialize(self, pr_number: int) -> MissionView:
        """Re-derive the gated fix-it mission for a PR (the operate.py path) so the Details page can
        show diagnosis + diff and offer approve/reject. Opens an in-memory mission only; nothing is
        pushed. GitHubError is returned as an ``error`` state rather than raised."""
        try:
            pull = self._find_pr(pr_number)
            if pull is None:
                return MissionView(
                    state="not_found",
                    pr_number=pr_number,
                    repo=self._repo,
                    message=f"No open PR #{pr_number} on {self._repo}.",
                )
            run = self._github.latest_run_for_branch(pull.head_branch)
            observational = _observational_state(run)
            if observational is not None:
                return self._view(pull, state=observational[0], message=observational[1])
            assert run is not None  # _observational_state returns None only when run is a failure
            return self._materialize_failure(pull, run)
        except GitHubError as exc:
            return MissionView(
                state="error",
                pr_number=pr_number,
                repo=self._repo,
                message=f"GitHub error: {exc}",
            )

    def _materialize_failure(self, pull: PullRequest, run: WorkflowRun) -> MissionView:
        result = analyze_run_failure(self._github, run.id, repo_root=self._repo_root)
        if result is None:
            return self._view(
                pull, state="no_failing_step", message="CI failed but no failing step was found."
            )
        step, analysis = result
        runtime = FixItRuntime(
            propose=AnalysisProposer(analysis, self._repo_root),
            runner=self._git,
            repo_root=self._repo_root,
            store=self._store,
        )
        mission = runtime.open_fix_it(analysis.summary)
        awaiting = mission.status is MissionStatus.AWAITING_APPROVAL
        diff = extract_diff(mission.step_results[0].output) if mission.step_results else None
        return MissionView(
            state="awaiting_approval" if awaiting else "no_patch",
            pr_number=pull.number,
            repo=self._repo,
            head_branch=pull.head_branch,
            html_url=pull.html_url,
            mission_id=mission.id,
            mission_status=mission.status.value,
            category=analysis.category,
            confidence=analysis.confidence,
            summary=analysis.summary,
            findings=[
                FindingView(file=f.file, line=f.line, code=f.code, message=f.message)
                for f in analysis.findings
            ],
            affected_files=list(analysis.affected_files),
            diff=diff,
            failing_job=step.job_name,
            failing_step=step.step_name,
            approval_reason=mission.approval.reason if mission.approval is not None else None,
            message=None
            if awaiting
            else "The Developer diagnosed but produced no patch — human intervention required; "
            "the mission ended fail-safe, so there is nothing to approve.",
        )

    # --- act (the EXISTING approval gate) ----------------------------------------------------

    def approve(self, mission_id: str, *, pr_number: int | None = None) -> DecisionResult:
        """Approve a materialized mission through the existing gateway: apply → commit → push →
        open_pr → COMPLETED. Raises ApprovalError if the id is unknown (e.g. re-derive it first)."""
        mission = self._gateway().approve(mission_id)
        return self._record("approved", mission, pr_number)

    def reject(self, mission_id: str, *, pr_number: int | None = None) -> DecisionResult:
        """Reject a materialized mission via the existing gateway: CANCELLED, no repo change."""
        mission = self._gateway().reject(mission_id)
        return self._record("rejected", mission, pr_number)

    # --- internals ---------------------------------------------------------------------------

    def _gateway(self) -> ApprovalGateway:
        return ApprovalGateway(self._store, repo_root=self._repo_root, git_runner=self._git)

    def _record(self, action: str, mission: Mission, pr_number: int | None) -> DecisionResult:
        output = mission.step_results[-1].output if mission.step_results else ""
        pr_url_match = _PR_URL_RE.search(output)
        if self._actions is not None:
            self._actions.record(
                action, mission_id=mission.id, status=mission.status.value, pr_number=pr_number
            )
        return DecisionResult(
            action=action,
            mission_id=mission.id,
            status=mission.status.value,
            pr_number=pr_number,
            pr_url=pr_url_match.group(0) if pr_url_match is not None else None,
            output=output,
        )

    def _find_pr(self, pr_number: int) -> PullRequest | None:
        return next(
            (pr for pr in self._github.open_pull_requests() if pr.number == pr_number), None
        )

    def _safe_latest_run(self, branch: str) -> WorkflowRun | None:
        try:
            return self._github.latest_run_for_branch(branch)
        except GitHubError:
            return None

    def _view(self, pull: PullRequest, *, state: str, message: str) -> MissionView:
        return MissionView(
            state=state,
            pr_number=pull.number,
            repo=self._repo,
            head_branch=pull.head_branch,
            html_url=pull.html_url,
            message=message,
        )


def _ci_status(run: WorkflowRun | None) -> str:
    if run is None:
        return "no_run"
    if run.is_pending:
        return "pending"
    if run.is_success:
        return "green"
    if run.is_failure:
        return "failing"
    return "unknown"


def _observational_state(run: WorkflowRun | None) -> tuple[str, str] | None:
    """Non-actionable states (no gated mission to open). Returns ``None`` only when the run is a
    failure — the one case ``materialize`` proceeds to re-derive a mission."""
    if run is None:
        return "no_run", "No CI run for this branch yet."
    if run.is_pending:
        return "pending", "CI is still running — nothing to decide yet."
    if run.is_success:
        return "green", "CI is green — nothing to fix."
    if not run.is_failure:
        return "unknown", "CI run in an unrecognized state."
    return None
