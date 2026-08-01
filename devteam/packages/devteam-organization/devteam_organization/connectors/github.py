"""GitHub connector — reuses the existing ``GitHubActions`` integration (no duplication) (§11).

Provides the CI signal the CTO reviews: the latest failed build and the open pull requests. The
extended categories the spec lists (releases, issues, Dependabot/code/secret-scanning alerts
alerts) are declared as empty lists here — the seam to add them is one method each on the connector,
never a new integration in a job. A GitHub outage or missing repo is Unavailable, never an error.
"""

from __future__ import annotations

from devteam_github import GitHubActions, GitHubError
from devteam_protocol import AgentRole

from devteam_organization.connectors.framework import ConnectorResult, ConnectorType


class GitHubConnector:
    id = "github"
    name = "GitHub"
    type = ConnectorType.GITHUB
    owner = AgentRole.CTO

    def __init__(self, github: GitHubActions | None) -> None:
        self._github = github

    @property
    def enabled(self) -> bool:
        return self._github is not None

    def fetch(self) -> ConnectorResult:
        if self._github is None:
            return ConnectorResult.unavailable("no repository configured")
        try:
            failure = self._github.latest_failure()
            prs = self._github.open_pull_requests()
        except GitHubError as exc:
            return ConnectorResult.unavailable(f"github unavailable: {exc}")
        latest = (
            {"summary": failure.summary, "head_branch": failure.head_branch}
            if failure is not None
            else None
        )
        return ConnectorResult.okay(
            {
                "latest_failure": latest,
                "open_prs": [
                    {"number": pr.number, "head_branch": pr.head_branch, "url": pr.html_url}
                    for pr in prs
                ],
                # Extended categories — the seam to add (a GitHubActions method + a line).
                "releases": [],
                "issues": [],
                "security_alerts": [],
                "dependabot": [],
                "code_scanning": [],
                "secret_scanning": [],
            }
        )
