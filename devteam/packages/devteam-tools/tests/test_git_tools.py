from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devteam_tools import (
    ApplyPatchTool,
    CommandResult,
    CommitChangesTool,
    OpenPrTool,
    PushBranchTool,
    branch_name,
    extract_diff,
)
from pipeline_contracts import TenantContext
from tool_registry.result import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT, ToolStepResult
from tool_registry.spec import SideEffectProfile


class FakeCommandRunner:
    """Records each command and returns queued results (default: success). No real subprocess."""

    def __init__(self, results: Sequence[CommandResult] | None = None) -> None:
        self.calls: list[tuple[tuple[str, ...], Path, str | None]] = []
        self._results = list(results or [])

    def run(
        self, args: Sequence[str], *, cwd: Path, stdin: str | None = None
    ) -> CommandResult:
        self.calls.append((tuple(args), cwd, stdin))
        return self._results.pop(0) if self._results else CommandResult(0, "", "")


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="platform", principal_id="foreman")


_DIFF = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
_FENCED = f"Developer: patch proposed\n```diff\n{_DIFF}```\n"


def test_all_git_tools_declare_consequential() -> None:
    runner = FakeCommandRunner()
    for tool in (
        ApplyPatchTool("/repo", runner),
        CommitChangesTool("/repo", runner),
        PushBranchTool("/repo", runner),
        OpenPrTool("/repo", runner),
    ):
        assert tool.spec.side_effect is SideEffectProfile.CONSEQUENTIAL
        assert tool.spec.is_consequential


def test_extract_diff_from_a_fenced_block_raw_or_missing() -> None:
    assert extract_diff(_FENCED) == _DIFF
    raw = "noise\ndiff --git a/x b/x\n@@ -1 +1 @@\n-o\n+n\n"
    assert extract_diff(raw) == "diff --git a/x b/x\n@@ -1 +1 @@\n-o\n+n\n"
    assert extract_diff("no patch here") is None


def test_branch_name_slugifies_or_defaults() -> None:
    assert branch_name("fix(ci): null deref") == "devteam/fix-ci-null-deref"
    assert branch_name("   ") == "devteam/fix"


def test_apply_patch_feeds_the_extracted_diff_to_git_apply() -> None:
    runner = FakeCommandRunner()
    tool = ApplyPatchTool("/repo", runner)
    result = ToolStepResult.from_payload(
        tool.invoke({PAYLOAD_PRIOR_CONTEXT: _FENCED}, _tenant())
    )
    assert result.ok is True
    (args, cwd, stdin) = runner.calls[0]
    assert args == ("git", "apply", "--whitespace=nowarn")
    assert cwd == Path("/repo")
    assert stdin == _DIFF  # the diff is piped in, not written to a temp file


def test_apply_patch_fails_safe_when_no_diff_is_present() -> None:
    runner = FakeCommandRunner()
    tool = ApplyPatchTool("/repo", runner)
    result = ToolStepResult.from_payload(
        tool.invoke({PAYLOAD_PRIOR_CONTEXT: "just a diagnosis, no patch"}, _tenant())
    )
    assert result.ok is False
    assert not runner.calls  # never touched git


def test_commit_changes_stages_then_commits_with_the_instruction_message() -> None:
    runner = FakeCommandRunner()
    tool = CommitChangesTool("/repo", runner)
    result = ToolStepResult.from_payload(
        tool.invoke({PAYLOAD_INSTRUCTION: "fix(ci): resolve null deref"}, _tenant())
    )
    assert result.ok is True
    assert runner.calls[0][0] == ("git", "add", "-A")
    assert runner.calls[1][0] == ("git", "commit", "-m", "fix(ci): resolve null deref")


def test_commit_changes_fails_safe_and_skips_commit_when_staging_fails() -> None:
    runner = FakeCommandRunner([CommandResult(1, "", "nothing to add")])
    tool = CommitChangesTool("/repo", runner)
    result = ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: "msg"}, _tenant()))
    assert result.ok is False
    assert len(runner.calls) == 1  # commit never attempted after a failed add


def test_push_branch_pushes_head_to_the_derived_remote_branch() -> None:
    runner = FakeCommandRunner()
    tool = PushBranchTool("/repo", runner)
    result = ToolStepResult.from_payload(
        tool.invoke({PAYLOAD_INSTRUCTION: "fix ci null deref"}, _tenant())
    )
    assert result.ok is True
    assert runner.calls[0][0] == (
        "git", "push", "-u", "origin", "HEAD:devteam/fix-ci-null-deref",
    )


def test_open_pr_creates_a_pr_and_surfaces_the_url() -> None:
    runner = FakeCommandRunner([CommandResult(0, "https://github.com/o/r/pull/7\n", "")])
    tool = OpenPrTool("/repo", runner)
    result = ToolStepResult.from_payload(
        tool.invoke(
            {PAYLOAD_INSTRUCTION: "Fix CI null deref", PAYLOAD_PRIOR_CONTEXT: "root cause: X"},
            _tenant(),
        )
    )
    assert result.ok is True
    assert "https://github.com/o/r/pull/7" in result.output
    (args, _cwd, _stdin) = runner.calls[0]
    assert args[:3] == ("gh", "pr", "create")
    assert "Fix CI null deref" in args


def test_open_pr_fails_safe_on_gh_error() -> None:
    runner = FakeCommandRunner([CommandResult(1, "", "gh: not authenticated")])
    tool = OpenPrTool("/repo", runner)
    result = ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: "t"}, _tenant()))
    assert result.ok is False
    assert result.warnings and "not authenticated" in result.warnings[0]
