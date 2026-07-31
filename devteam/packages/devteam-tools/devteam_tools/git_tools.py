"""The consequential Git Tools (ADR 0061/0062) — reasoning's execution backend, gated by the Core.

The Developer agent's job ends at a patch artifact; applying it is a Tool, not agent behavior. These
four Tools declare ``SideEffectProfile.CONSEQUENTIAL``, so the Mission Engine pauses the mission at
the ADR 0044 human approval gate before the first one runs; after approval it resumes and they land
the change: apply_patch -> commit_changes -> push_branch -> open_pr. Each reads its input from the
step — the commit message / branch / PR title from the instruction, the diff / PR body from the
prior context (ADR 0051) — and shells out through an injected ``CommandRunner``, mapping the outcome
to the canonical ``ToolStepResult`` (``ok=False`` on a failed command, so the Core fails safe).
"""

from __future__ import annotations

import re
from pathlib import Path

from pipeline_contracts import TenantContext
from tool_registry.result import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT, ToolStepResult
from tool_registry.spec import SideEffectProfile, ToolSpec

from devteam_tools.command_runner import CommandResult, CommandRunner
from devteam_tools.names import APPLY_PATCH, COMMIT_CHANGES, OPEN_PR, PUSH_BRANCH

_DIFF_FENCE = re.compile(r"```diff\n(.*?)```", re.DOTALL)
_SLUG = re.compile(r"[^a-z0-9]+")
_DEFAULT_BRANCH = "devteam/fix"


def extract_diff(text: str) -> str | None:
    """Pull a unified diff out of the Developer's prior output: the contents of a ```diff fenced
    block if present, else the text from the first ``diff --git`` onward, else ``None``."""
    fenced = _DIFF_FENCE.search(text)
    if fenced is not None:
        return fenced.group(1)
    index = text.find("diff --git")
    return text[index:] if index != -1 else None


def branch_name(instruction: str) -> str:
    """A safe remote branch name from the step instruction (slugified), or a default. Keeps the
    dev team's branches namespaced under ``devteam/`` so they are easy to spot and clean up."""
    slug = _SLUG.sub("-", instruction.strip().lower()).strip("-")
    return f"devteam/{slug}" if slug else _DEFAULT_BRANCH


def _result(command: CommandResult, ok_summary: str) -> dict[str, object]:
    """Map a command outcome to the canonical result: the summary on success; ``ok=False`` with the
    captured error as a warning on failure, so the Mission Engine fails the step safely."""
    if command.ok:
        return ToolStepResult(ok=True, output=ok_summary).as_payload()
    detail = command.stderr.strip() or command.stdout.strip() or f"exit {command.code}"
    return ToolStepResult(ok=False, output=ok_summary, warnings=(detail,)).as_payload()


class ApplyPatchTool:
    """Apply the Developer's proposed unified diff to the working tree with ``git apply``.
    Consequential — gated by the Core before it runs. Fails safe if there is no diff to apply."""

    def __init__(self, repo_root: Path | str, runner: CommandRunner) -> None:
        self._repo_root = Path(repo_root)
        self._runner = runner

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=APPLY_PATCH,
            version=1,
            description="Apply a unified diff to the working tree (consequential).",
            side_effect=SideEffectProfile.CONSEQUENTIAL,
        )

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        diff = extract_diff(str(payload.get(PAYLOAD_PRIOR_CONTEXT, "")))
        if diff is None:
            return ToolStepResult(
                ok=False,
                output="apply_patch: no diff found in prior context",
                warnings=("the Developer step produced no diff to apply",),
            ).as_payload()
        result = self._runner.run(
            ["git", "apply", "--whitespace=nowarn"], cwd=self._repo_root, stdin=diff
        )
        return _result(result, "apply_patch: applied the proposed diff to the working tree")


class CommitChangesTool:
    """Stage all changes and commit them (``git add -A`` + ``git commit``); the commit message is
    the step instruction. Consequential — gated by the Core before it runs."""

    def __init__(self, repo_root: Path | str, runner: CommandRunner) -> None:
        self._repo_root = Path(repo_root)
        self._runner = runner

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=COMMIT_CHANGES,
            version=1,
            description="Stage all changes and commit them (consequential).",
            side_effect=SideEffectProfile.CONSEQUENTIAL,
        )

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        message = str(payload.get(PAYLOAD_INSTRUCTION, "")).strip() or "chore(devteam): apply patch"
        staged = self._runner.run(["git", "add", "-A"], cwd=self._repo_root)
        if not staged.ok:
            return _result(staged, "commit_changes: staging (git add) failed")
        committed = self._runner.run(["git", "commit", "-m", message], cwd=self._repo_root)
        return _result(committed, f"commit_changes: committed with message {message!r}")


class PushBranchTool:
    """Push HEAD to a remote branch (``git push -u origin HEAD:<branch>``). The branch is derived
    from the step instruction. Consequential — gated by the Core; needs a real remote + creds."""

    def __init__(self, repo_root: Path | str, runner: CommandRunner) -> None:
        self._repo_root = Path(repo_root)
        self._runner = runner

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=PUSH_BRANCH,
            version=1,
            description="Push HEAD to a remote branch (consequential).",
            side_effect=SideEffectProfile.CONSEQUENTIAL,
        )

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        branch = branch_name(str(payload.get(PAYLOAD_INSTRUCTION, "")))
        result = self._runner.run(
            ["git", "push", "-u", "origin", f"HEAD:{branch}"], cwd=self._repo_root
        )
        return _result(result, f"push_branch: pushed HEAD to origin/{branch}")


class OpenPrTool:
    """Open a pull request for the pushed branch (``gh pr create``). Title from the instruction,
    body from the prior context. Consequential — gated by the Core; needs a real remote + creds."""

    def __init__(self, repo_root: Path | str, runner: CommandRunner) -> None:
        self._repo_root = Path(repo_root)
        self._runner = runner

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=OPEN_PR,
            version=1,
            description="Open a pull request for the pushed branch (consequential).",
            side_effect=SideEffectProfile.CONSEQUENTIAL,
        )

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        title = str(payload.get(PAYLOAD_INSTRUCTION, "")).strip() or "Automated fix by the dev team"
        body = str(payload.get(PAYLOAD_PRIOR_CONTEXT, "")).strip() or "Opened by the dev team."
        result = self._runner.run(
            ["gh", "pr", "create", "--title", title, "--body", body], cwd=self._repo_root
        )
        # gh prints the new PR's URL on success — surface it so downstream monitoring can find it.
        summary = f"open_pr: {result.stdout.strip()}" if result.ok and result.stdout.strip() else (
            f"open_pr: opened a pull request titled {title!r}"
        )
        return _result(result, summary)
