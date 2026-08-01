"""Registered dev-tool names — the stable identifiers plans route to via ``PlanStep.tool``
(ADR 0048) and the registry resolves. Named constants, never magic strings (CLAUDE.md §21)."""

from __future__ import annotations

# Read-only: report basic health facts about a target repository working tree.
CHECK_REPO_HEALTH = "check_repo_health"

# Consequential: apply a unified diff to the working tree.
APPLY_PATCH = "apply_patch"
# Consequential: stage all changes and commit them.
COMMIT_CHANGES = "commit_changes"
# Consequential: push HEAD to a remote branch.
PUSH_BRANCH = "push_branch"
# Consequential: open a pull request for the pushed branch.
OPEN_PR = "open_pr"
