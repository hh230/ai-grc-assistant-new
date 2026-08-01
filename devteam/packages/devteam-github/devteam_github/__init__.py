"""Autonomous Platform Dev Team — GitHub connector (ADR 0061; §17 plugin).

The only GitHub-aware layer: a real adapter that watches a repository's Actions runs over the REST
API (curl through the injected CommandRunner — no new HTTP dependency) and surfaces the latest CI
failure as a WorkflowRun, the real trigger that opens a fix-it mission. Read-only — it observes CI.
"""

from devteam_github.client import (
    FailingStep,
    GitHubActions,
    GitHubError,
    PullRequest,
    WorkflowRun,
)

__all__ = ["FailingStep", "GitHubActions", "GitHubError", "PullRequest", "WorkflowRun"]
