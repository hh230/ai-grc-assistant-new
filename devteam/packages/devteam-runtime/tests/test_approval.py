"""The ApprovalGateway closes the chain's attempt cycle: a gated mission -> human decision -> the
mission becomes terminal on the SHARED store -> the ChainDriver advances (or the chain goes green).

Two levels: the gateway in isolation (approve/reject a mission by id over a shared store, no chain),
and the full cycle end to end (a canned GitHubActions + build_chain_driver + gateway over one store:
attempt 1 opens gated, an approval lands it to COMPLETED, the next poll opens attempt 2). Git is a
fake runner (no real repo/remote); no network — the GitHub connector runs a canned CommandRunner.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from devteam_contracts import platform_tenant
from devteam_github import GitHubActions
from devteam_protocol import AgentArtifact, AgentRequest
from devteam_runtime import (
    ApprovalError,
    ApprovalGateway,
    ChainStatus,
    FixItRuntime,
    build_chain_driver,
)
from devteam_tools import CommandResult
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.lifecycle import MissionStatus

_DIFF = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"


class FakeGit:
    """Records git/gh calls and returns success — plus a PR url for ``gh pr`` so open_pr passes."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        self.calls.append(tuple(args))
        if tuple(args[:2]) == ("gh", "pr"):
            return CommandResult(0, "https://github.com/o/r/pull/1\n", "")
        return CommandResult(0, "", "")


class QueueRunner:
    """Pops queued CommandResults in order — the canned curl sequence for the GitHub connector."""

    def __init__(self, results: Sequence[CommandResult]) -> None:
        self._results = list(results)

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        return self._results.pop(0) if self._results else CommandResult(0, "", "")


def _with_patch(_request: AgentRequest) -> list[AgentArtifact]:
    return [
        AgentArtifact(kind="diagnosis", title="root cause", content="null deref"),
        AgentArtifact(kind="diff", title="fix", content=_DIFF),
    ]


# --- the gateway in isolation ---------------------------------------------------------------


def test_gateway_approves_a_pending_mission_by_id_and_lands_it() -> None:
    store, git = InMemoryMissionStore(), FakeGit()
    opener = FixItRuntime(propose=_with_patch, runner=git, repo_root="/repo", store=store)
    mission = opener.open_fix_it("bug")  # gated, in the shared store
    assert mission.status is MissionStatus.AWAITING_APPROVAL

    gateway = ApprovalGateway(store, repo_root="/repo", git_runner=git)
    assert gateway.pending(mission.id) is not None  # reviewable before deciding
    landed = gateway.approve(mission.id)

    assert landed.status is MissionStatus.COMPLETED
    # the store — the chain's single source of truth — now holds the terminal mission
    stored = store.get(mission.id, platform_tenant())
    assert stored is not None and stored.status is MissionStatus.COMPLETED
    assert [c[:2] for c in git.calls] == [
        ("git", "apply"),
        ("git", "add"),
        ("git", "commit"),
        ("git", "push"),
        ("gh", "pr"),
    ]


def test_gateway_rejects_a_pending_mission_by_id_without_touching_the_repo() -> None:
    store, git = InMemoryMissionStore(), FakeGit()
    mission = FixItRuntime(
        propose=_with_patch, runner=git, repo_root="/repo", store=store
    ).open_fix_it("bug")

    rejected = ApprovalGateway(store, repo_root="/repo", git_runner=git).reject(mission.id)

    assert rejected.status is MissionStatus.CANCELLED
    assert git.calls == []  # rejected before any side effect


def test_gateway_raises_on_an_unknown_mission() -> None:
    gateway = ApprovalGateway(InMemoryMissionStore(), repo_root="/repo", git_runner=FakeGit())
    with pytest.raises(ApprovalError):
        gateway.approve("does-not-exist")


# --- the full attempt cycle -----------------------------------------------------------------

_JOBS = json.dumps(
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
_LOG = "2024-01-01T00:00:01Z src/x.py:3: error: Missing return type  [no-untyped-def]\n"
_RED = json.dumps(
    {
        "workflow_runs": [
            {
                "id": 7,
                "name": "CI",
                "status": "completed",
                "conclusion": "failure",
                "head_branch": "pr-1",
                "display_title": "fix",
                "html_url": "u",
            }
        ]
    }
)


def _github_two_opens() -> GitHubActions:
    # Two openings: each = latest_run_for_branch (red) -> find_failing_step -> download_job_log.
    runner = QueueRunner(
        [
            CommandResult(0, _RED, ""),
            CommandResult(0, _JOBS, ""),
            CommandResult(0, _LOG, ""),
            CommandResult(0, _RED, ""),
            CommandResult(0, _JOBS, ""),
            CommandResult(0, _LOG, ""),
        ]
    )
    return GitHubActions(runner, "o/r", token="t")


def _seed_source(tmp_path: Path) -> None:
    # The Developer reads real source to build a diff (so the mission gates); src/x.py:3 is the
    # log's finding. Without it the Developer declines and the mission ends CANCELLED, not gated.
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "x.py").write_text("def f():\n    pass\n    return None\n")


def test_approval_completes_attempt_1_then_the_chain_opens_attempt_2(tmp_path: Path) -> None:
    _seed_source(tmp_path)
    store, git = InMemoryMissionStore(), FakeGit()
    driver = build_chain_driver(
        _github_two_opens(), repo_root=tmp_path, git_runner=git, mission_store=store
    )
    gateway = ApprovalGateway(store, repo_root=tmp_path, git_runner=git)

    first = driver.advance("issue-1", "pr-1")  # attempt 1 opens, paused at the gate
    assert first.status is ChainStatus.OPENED
    assert first.mission is not None and first.mission.status is MissionStatus.AWAITING_APPROVAL

    landed = gateway.approve(first.mission.id)  # a human approves → the patch lands
    assert landed.status is MissionStatus.COMPLETED

    second = driver.advance("issue-1", "pr-1")  # still red, attempt 1 finished → open attempt 2
    assert second.status is ChainStatus.OPENED
    assert second.attempt is not None and second.attempt.attempt_number == 2
    assert second.mission is not None and second.mission.id != first.mission.id


def test_rejection_finishes_attempt_1_then_the_chain_opens_attempt_2(tmp_path: Path) -> None:
    _seed_source(tmp_path)
    store, git = InMemoryMissionStore(), FakeGit()
    driver = build_chain_driver(
        _github_two_opens(), repo_root=tmp_path, git_runner=git, mission_store=store
    )
    gateway = ApprovalGateway(store, repo_root=tmp_path, git_runner=git)

    first = driver.advance("issue-1", "pr-1")
    assert first.mission is not None
    gateway.reject(first.mission.id)  # a human rejects → CANCELLED (terminal)

    second = driver.advance("issue-1", "pr-1")  # attempt 1 finished → the chain still advances
    assert second.status is ChainStatus.OPENED
    assert second.attempt is not None and second.attempt.attempt_number == 2
