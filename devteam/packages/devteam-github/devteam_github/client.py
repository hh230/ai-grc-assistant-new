"""GitHubActions — the dev team's GitHub connector (ADR 0061; §17 plugin).

The only GitHub-aware layer: a real adapter over the GitHub Actions REST API. It runs curl through
the injected CommandRunner (the same seam the Git Tools use — no new HTTP dependency), so it stays
deterministic and testable: production injects SubprocessCommandRunner (real network), tests inject
a fake returning canned JSON. It reads a repository's recent workflow runs and surfaces the latest
CI failure as a WorkflowRun, finds the failing job/step, and downloads the failing job's real log —
the real failure context a fix-it mission reasons over. Read-only: it observes CI, never changes it.

Auth: listing runs/jobs is public for public repos; DOWNLOADING logs requires a token even then. The
token rides a curl --config on stdin, so it never appears in argv (or in any raised error).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from devteam_tools import CommandResult, CommandRunner

_API_BASE = "https://api.github.com"


class GitHubError(RuntimeError):
    """A GitHub query failed: curl error, an unparseable response, or rejected auth."""


@dataclass(frozen=True)
class WorkflowRun:
    """One GitHub Actions run, trimmed to what the dev team needs to detect a CI failure.
    ``conclusion`` is empty until the run completes (queued/in_progress have no verdict yet)."""

    id: int
    name: str
    status: str
    conclusion: str
    head_branch: str
    display_title: str
    html_url: str

    @property
    def is_failure(self) -> bool:
        return self.status == "completed" and self.conclusion == "failure"

    @property
    def is_success(self) -> bool:
        return self.status == "completed" and self.conclusion == "success"

    @property
    def is_pending(self) -> bool:
        """Still queued or running — no verdict yet (continue-until-green keeps waiting)."""
        return self.status != "completed"

    @property
    def summary(self) -> str:
        """A one-line issue summary for the fix-it mission the failure opens."""
        return f"CI failure: {self.name} on {self.head_branch} — {self.display_title}"


@dataclass(frozen=True)
class FailingStep:
    """The failing job + step in a run — enough to download the right job's log and describe it."""

    job_id: int
    job_name: str
    step_name: str
    step_number: int


@dataclass(frozen=True)
class PullRequest:
    """One open pull request, trimmed to what the continuous monitor needs to watch its CI chain:
    the head branch (whose latest run is the verdict) and a stable key for its fix attempts."""

    number: int
    head_branch: str
    title: str
    html_url: str

    @property
    def correlation_ref(self) -> str:
        """The stable chain key this PR's fix attempts group under (its number never changes)."""
        return f"pr-{self.number}"


class GitHubActions:
    """Reads a repository's Actions runs/jobs/logs over the REST API via curl (through the
    CommandRunner). ``repo`` is ``owner/name``; ``token`` (read from the environment by the caller)
    is required only to download logs. Read-only — it observes CI."""

    def __init__(
        self,
        runner: CommandRunner,
        repo: str,
        *,
        token: str | None = None,
        api_base: str = _API_BASE,
    ) -> None:
        self._runner = runner
        self._repo = repo
        self._token = token
        self._api_base = api_base.rstrip("/")

    def list_runs(self, *, per_page: int = 20) -> list[WorkflowRun]:
        """The most recent workflow runs, newest first (as GitHub returns them). Public."""
        result = self._get(
            f"{self._api_base}/repos/{self._repo}/actions/runs?per_page={per_page}"
        )
        if not result.ok:
            raise GitHubError(f"could not query runs for {self._repo}: exit {result.code}")
        return _parse_runs(result.stdout)

    def latest_run_for_branch(self, branch: str) -> WorkflowRun | None:
        """The most recent workflow run on a branch (a PR's head branch) — its verdict (is_success /
        is_failure / is_pending) is what the continue-until-green loop watches. None if none yet."""
        query = f"branch={quote(branch, safe='')}&per_page=1"
        result = self._get(f"{self._api_base}/repos/{self._repo}/actions/runs?{query}")
        if not result.ok:
            raise GitHubError(f"could not query runs for branch {branch}: exit {result.code}")
        runs = _parse_runs(result.stdout)
        return runs[0] if runs else None

    def open_pull_requests(self, *, per_page: int = 100) -> list[PullRequest]:
        """The repository's open pull requests — the set the continuous monitor watches (it advances
        each one's head-branch CI chain). Public for public repos. One page: enough for the Worker;
        pagination is a later concern if a repo ever holds more than ``per_page`` open PRs."""
        result = self._get(
            f"{self._api_base}/repos/{self._repo}/pulls?state=open&per_page={per_page}"
        )
        if not result.ok:
            raise GitHubError(f"could not list pull requests for {self._repo}: exit {result.code}")
        return _parse_pulls(result.stdout)

    def latest_failure(self) -> WorkflowRun | None:
        """The most recent FAILED run, or None if none of the recent runs failed."""
        return next((run for run in self.list_runs() if run.is_failure), None)

    def find_failing_step(self, run_id: int) -> FailingStep | None:
        """The first failing step of the first failing job in a run, from the public jobs API."""
        result = self._get(
            f"{self._api_base}/repos/{self._repo}/actions/runs/{run_id}/jobs?per_page=50"
        )
        if not result.ok:
            raise GitHubError(f"could not list jobs for run {run_id}: exit {result.code}")
        return _first_failing_step(result.stdout)

    def download_job_log(self, job_id: int) -> str:
        """The failing job's real log text (all steps). Requires a token — raises otherwise."""
        result = self._get(
            f"{self._api_base}/repos/{self._repo}/actions/jobs/{job_id}/logs", authed=True
        )
        if not result.ok:
            raise GitHubError(f"could not download logs for job {job_id}: exit {result.code}")
        error = _api_error_message(result.stdout)
        if error is not None:
            raise GitHubError(f"GitHub rejected the log for job {job_id}: {error}")
        return result.stdout

    def _get(self, url: str, *, authed: bool = False) -> CommandResult:
        if not authed:
            return self._runner.run(
                ["curl", "-s", "-H", "Accept: application/vnd.github+json", url], cwd=Path(".")
            )
        if not self._token:
            raise GitHubError("this GitHub request requires a token (set GITHUB_TOKEN)")
        # The token rides a --config on stdin, never argv — so it stays out of the process table
        # and out of any GitHubError we raise (which only ever mention the URL/status).
        config = (
            "silent\nlocation\n"
            'header = "Accept: application/vnd.github+json"\n'
            f'header = "Authorization: Bearer {self._token}"\n'
            f'url = "{url}"\n'
        )
        return self._runner.run(["curl", "--config", "-"], cwd=Path("."), stdin=config)


def _parse_runs(body: str) -> list[WorkflowRun]:
    data = _load(body)
    if not isinstance(data, dict):
        return []
    runs = data.get("workflow_runs")
    if not isinstance(runs, list):
        return []
    return [_to_run(item) for item in runs if isinstance(item, dict)]


def _parse_pulls(body: str) -> list[PullRequest]:
    # GitHub's /pulls returns a bare JSON array (not an object with a key, unlike /actions/runs).
    data = _load(body)
    if not isinstance(data, list):
        return []
    return [_to_pull(item) for item in data if isinstance(item, dict)]


def _to_pull(item: dict[str, object]) -> PullRequest:
    head = item.get("head")
    branch = head.get("ref") if isinstance(head, dict) else None
    return PullRequest(
        number=_as_int(item.get("number")),
        head_branch=_as_str(branch),
        title=_as_str(item.get("title")),
        html_url=_as_str(item.get("html_url")),
    )


def _first_failing_step(body: str) -> FailingStep | None:
    data = _load(body)
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return None
    for job in jobs:
        if not isinstance(job, dict) or job.get("conclusion") != "failure":
            continue
        steps = job.get("steps")
        for step in steps if isinstance(steps, list) else []:
            if isinstance(step, dict) and step.get("conclusion") == "failure":
                return FailingStep(
                    job_id=_as_int(job.get("id")),
                    job_name=_as_str(job.get("name")),
                    step_name=_as_str(step.get("name")),
                    step_number=_as_int(step.get("number")),
                )
    return None


def _load(body: str) -> object:
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise GitHubError(f"invalid JSON from GitHub: {exc}") from exc


def _api_error_message(body: str) -> str | None:
    """GitHub's error message if the body is a JSON error object (a 403/404 in place of a log), else
    None. The message names the reason (bad credentials, missing scope, …) and never the token."""
    head = body.lstrip()
    if not head.startswith("{"):
        return None
    try:
        data = json.loads(head)
    except json.JSONDecodeError:
        return None
    message = data.get("message") if isinstance(data, dict) else None
    return message if isinstance(message, str) else None


def _to_run(item: dict[str, object]) -> WorkflowRun:
    return WorkflowRun(
        id=_as_int(item.get("id")),
        name=_as_str(item.get("name")),
        status=_as_str(item.get("status")),
        conclusion=_as_str(item.get("conclusion")),
        head_branch=_as_str(item.get("head_branch")),
        display_title=_as_str(item.get("display_title")),
        html_url=_as_str(item.get("html_url")),
    )


def _as_str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
