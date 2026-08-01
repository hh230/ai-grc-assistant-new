"""Shared test doubles — a fake GitHub (duck-typing GitHubActions) and a fake git runner, mirroring
the runtime's own approval tests. No network, no real repo: one open PR whose latest run failed on a
mypy error, so the real analyzers + AnalysisProposer produce a real diff over seeded source.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devteam_github import FailingStep, PullRequest, WorkflowRun
from devteam_tools import CommandResult

# A mypy failing line the MypyAnalyzer recognizes; points at src/x.py:3 (seeded below).
MYPY_LOG = "2024-01-01T00:00:01Z src/x.py:3: error: Missing return type  [no-untyped-def]\n"


class FakeGit:
    """Records git/gh calls and returns success — plus a PR url for ``gh pr`` (test_approval)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        self.calls.append(tuple(args))
        if tuple(args[:2]) == ("gh", "pr"):
            return CommandResult(0, "https://github.com/o/r/pull/1\n", "")
        return CommandResult(0, "", "")


class FakeGitHub:
    """Duck-types the GitHubActions surface the dashboard uses. Default: one open PR (pr-1) whose
    latest CI run failed. Pass ``pulls=[]`` for the empty case, or a custom run verdict."""

    def __init__(
        self, *, pulls: list[PullRequest] | None = None, run: WorkflowRun | None = None
    ) -> None:
        self._pulls = (
            pulls
            if pulls is not None
            else [PullRequest(1, "pr-1", "fix null deref", "https://github.com/o/r/pull/1")]
        )
        self._run = run if run is not None else WorkflowRun(
            7, "CI", "completed", "failure", "pr-1", "fix", "https://github.com/o/r/runs/7"
        )

    def open_pull_requests(self, *, per_page: int = 100) -> list[PullRequest]:
        return list(self._pulls)

    def latest_run_for_branch(self, branch: str) -> WorkflowRun | None:
        return self._run if branch == "pr-1" else None

    def list_runs(self, *, per_page: int = 20) -> list[WorkflowRun]:
        return [self._run]

    def find_failing_step(self, run_id: int) -> FailingStep | None:
        return FailingStep(200, "python", "Run uv run mypy .", 6)

    def download_job_log(self, job_id: int) -> str:
        return MYPY_LOG


def seed_source(root: Path) -> None:
    """The Developer reads real source to build a diff; src/x.py:3 is the log's finding. Without it
    the Developer declines and the mission ends CANCELLED (no patch) rather than gating."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "x.py").write_text("def f():\n    pass\n    return None\n")
