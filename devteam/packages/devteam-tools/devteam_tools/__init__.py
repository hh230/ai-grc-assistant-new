"""Autonomous Platform Dev Team — Dev Tools (ADR 0061).

Every capability the dev team performs is a registered ``Tool`` (frozen ``tool-registry`` contract:
``ToolSpec`` + ``ToolStepResult``), with a declared ``SideEffectProfile``. Read-only tools run
autonomously; consequential tools are gated by the Mission Engine before they run — the tool only
*declares* consequential, it never self-authorizes (ADR 0006/0042 §5). Tools depend only on
``tool-registry`` (+ ``pipeline-contracts``), never the LLM/orchestrator stack (ADR 0049).

The Git Tools (apply_patch, commit_changes, push_branch, open_pr) are the consequential execution
backend for a fix-it mission: the Developer proposes a diff, the human gate approves, and these land
it. They shell out through an injected ``CommandRunner`` (subprocess in prod, a fake in tests).
"""

from devteam_tools.command_runner import CommandResult, CommandRunner, SubprocessCommandRunner
from devteam_tools.git_tools import (
    ApplyPatchTool,
    CommitChangesTool,
    OpenPrTool,
    PushBranchTool,
    branch_name,
    extract_diff,
)
from devteam_tools.names import (
    APPLY_PATCH,
    CHECK_REPO_HEALTH,
    COMMIT_CHANGES,
    OPEN_PR,
    PUSH_BRANCH,
)
from devteam_tools.repo_health import CheckRepoHealthTool

__all__ = [
    "APPLY_PATCH",
    "CHECK_REPO_HEALTH",
    "COMMIT_CHANGES",
    "OPEN_PR",
    "PUSH_BRANCH",
    "ApplyPatchTool",
    "CheckRepoHealthTool",
    "CommandResult",
    "CommandRunner",
    "CommitChangesTool",
    "OpenPrTool",
    "PushBranchTool",
    "SubprocessCommandRunner",
    "branch_name",
    "extract_diff",
]
