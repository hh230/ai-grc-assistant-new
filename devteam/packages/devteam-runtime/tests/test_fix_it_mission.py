"""E2E: the gated fix-it mission on the frozen Core — Developer -> one gate -> land the patch.

Proves the target behavior for a single mission: the Developer diagnoses and proposes a diff, the
mission pauses ONCE at the human approval gate before any repository side effect, and a single
approval lands the whole sequence (apply -> commit -> push -> open PR). Rejection cancels fail-safe;
a missing patch fails safe after approval without committing. Git is a FakeCommandRunner — no real
repo, no real remote.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devteam_contracts import PLATFORM_TENANT_ID
from devteam_protocol import AgentArtifact, AgentRequest
from devteam_runtime import FixItRuntime
from devteam_tools import CommandResult
from mission_engine.lifecycle import MissionStatus

_DIFF = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"


class FakeCommandRunner:
    """Records each command and returns queued results (default: success). No real subprocess."""

    def __init__(self, results: Sequence[CommandResult] | None = None) -> None:
        self.calls: list[tuple[tuple[str, ...], Path, str | None]] = []
        self._results = list(results or [])

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        self.calls.append((tuple(args), cwd, stdin))
        return self._results.pop(0) if self._results else CommandResult(0, "", "")


def _with_patch(_request: AgentRequest) -> list[AgentArtifact]:
    return [
        AgentArtifact(kind="diagnosis", title="root cause", content="null deref"),
        AgentArtifact(kind="diff", title="fix", content=_DIFF),
    ]


def _no_patch(_request: AgentRequest) -> list[AgentArtifact]:
    return [AgentArtifact(kind="diagnosis", title="root cause", content="no fix yet")]


def test_fix_it_pauses_at_the_gate_after_the_developer_step() -> None:
    runner = FakeCommandRunner()
    runtime = FixItRuntime(propose=_with_patch, runner=runner, repo_root="/repo")
    mission = runtime.open_fix_it("null deref in parser")
    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert len(mission.step_results) == 1  # only the Developer ran; no git yet
    assert not runner.calls  # nothing touched the repo before approval


def test_one_approval_lands_the_whole_sequence() -> None:
    runner = FakeCommandRunner(
        [
            CommandResult(0, "", ""),  # git apply
            CommandResult(0, "", ""),  # git add
            CommandResult(0, "", ""),  # git commit
            CommandResult(0, "", ""),  # git push
            CommandResult(0, "https://github.com/o/r/pull/9\n", ""),  # gh pr create
        ]
    )
    runtime = FixItRuntime(propose=_with_patch, runner=runner, repo_root="/repo")
    mission = runtime.open_fix_it("null deref in parser")
    mission = runtime.approve_and_resume(mission)

    assert mission.status is MissionStatus.COMPLETED
    assert mission.tenant_id == PLATFORM_TENANT_ID
    assert len(mission.step_results) == 5  # developer + apply + commit + push + pr
    # the four git operations ran, in order, after the single approval
    assert [call[0][:2] for call in runner.calls] == [
        ("git", "apply"),
        ("git", "add"),
        ("git", "commit"),
        ("git", "push"),
        ("gh", "pr"),
    ]
    # the Developer's diff flowed across the (artifact-lossy) engine seam into git apply's stdin
    apply_stdin = runner.calls[0][2]
    assert apply_stdin is not None and _DIFF in apply_stdin
    assert "pull/9" in mission.step_results[-1].output  # the PR url is surfaced


def test_fix_it_audit_shows_one_gate_then_the_landing() -> None:
    runner = FakeCommandRunner()
    runtime = FixItRuntime(propose=_with_patch, runner=runner, repo_root="/repo")
    mission = runtime.open_fix_it("bug")
    runtime.approve_and_resume(mission)
    assert runtime.audit.event_names_for(mission.id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",  # developer
        "mission.awaiting_approval",  # the single gate
        "mission.approved",
        "mission.resumed",
        "mission.step_completed",  # apply
        "mission.step_completed",  # commit
        "mission.step_completed",  # push
        "mission.step_completed",  # open_pr
        "mission.completed",
    ]


def test_rejection_cancels_without_touching_the_repo() -> None:
    runner = FakeCommandRunner()
    runtime = FixItRuntime(propose=_with_patch, runner=runner, repo_root="/repo")
    mission = runtime.open_fix_it("bug")
    mission = runtime.reject(mission)
    assert mission.status is MissionStatus.CANCELLED
    assert not runner.calls  # rejected before any side effect


def test_no_patch_ends_without_a_meaningless_gate() -> None:
    # The Developer diagnosed but produced no patch: there is nothing to apply and so nothing to
    # approve. The mission ends fail-safe (human intervention required) — NOT paused at the gate.
    runner = FakeCommandRunner()
    runtime = FixItRuntime(propose=_no_patch, runner=runner, repo_root="/repo")
    mission = runtime.open_fix_it("bug")
    assert mission.status is MissionStatus.CANCELLED  # ended, no gate presented
    assert len(mission.step_results) == 1  # the Developer's diagnosis is still recorded
    assert not runner.calls  # nothing touched the repo — no apply/commit/push/pr
    # it ended via the no-patch path, not a plain cancel (the audit carries the reason)
    assert runtime.audit.event_names_for(mission.id)[-1] == "mission.cancelled"
