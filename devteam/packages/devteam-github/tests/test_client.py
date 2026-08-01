from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from devteam_github import FailingStep, GitHubActions, GitHubError, PullRequest, WorkflowRun
from devteam_tools import CommandResult


class FakeCommandRunner:
    """Returns one canned CommandResult and records (args, cwd, stdin) — no curl, no network."""

    def __init__(self, result: CommandResult) -> None:
        self.calls: list[tuple[tuple[str, ...], Path, str | None]] = []
        self._result = result

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        self.calls.append((tuple(args), cwd, stdin))
        return self._result


def _runs_json(*runs: dict[str, object]) -> str:
    return json.dumps({"total_count": len(runs), "workflow_runs": list(runs)})


_FAIL: dict[str, object] = {
    "id": 42,
    "name": "CI",
    "status": "completed",
    "conclusion": "failure",
    "head_branch": "develop",
    "display_title": "fix(ci): remove duplicate pnpm version",
    "html_url": "https://github.com/o/r/actions/runs/42",
}
_OK: dict[str, object] = {
    "id": 43,
    "name": "CI",
    "status": "completed",
    "conclusion": "success",
    "head_branch": "main",
    "display_title": "merge",
    "html_url": "https://github.com/o/r/actions/runs/43",
}
_RUNNING: dict[str, object] = {
    "id": 44,
    "name": "CI",
    "status": "in_progress",
    "conclusion": None,
    "head_branch": "main",
    "display_title": "wip",
    "html_url": "https://github.com/o/r/actions/runs/44",
}


def test_list_runs_parses_the_api_and_targets_the_repo_endpoint() -> None:
    runner = FakeCommandRunner(CommandResult(0, _runs_json(_OK, _FAIL), ""))
    runs = GitHubActions(runner, "o/r").list_runs()
    assert [run.id for run in runs] == [43, 42]  # newest first, as GitHub returns them
    args = runner.calls[0][0]
    assert args[0] == "curl"
    assert any("repos/o/r/actions/runs" in arg for arg in args)


def test_latest_failure_returns_the_most_recent_failed_run() -> None:
    runner = FakeCommandRunner(CommandResult(0, _runs_json(_OK, _FAIL, _RUNNING), ""))
    failure = GitHubActions(runner, "o/r").latest_failure()
    assert failure is not None
    assert failure.id == 42 and failure.is_failure
    assert failure.summary == "CI failure: CI on develop — fix(ci): remove duplicate pnpm version"


def test_latest_failure_is_none_when_ci_is_green() -> None:
    runner = FakeCommandRunner(CommandResult(0, _runs_json(_OK, _RUNNING), ""))
    assert GitHubActions(runner, "o/r").latest_failure() is None


def test_an_in_progress_run_is_not_a_failure() -> None:
    running = WorkflowRun(1, "CI", "in_progress", "", "main", "wip", "u")
    assert running.is_failure is False


def test_workflow_run_ci_verdicts() -> None:
    green = WorkflowRun(1, "CI", "completed", "success", "b", "t", "u")
    red = WorkflowRun(2, "CI", "completed", "failure", "b", "t", "u")
    running = WorkflowRun(3, "CI", "in_progress", "", "b", "t", "u")
    assert green.is_success and not green.is_failure and not green.is_pending
    assert red.is_failure and not red.is_success and not red.is_pending
    assert running.is_pending and not running.is_success and not running.is_failure


def test_latest_run_for_branch_targets_the_branch_and_returns_the_run() -> None:
    run: dict[str, object] = {
        "id": 9,
        "name": "CI",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "devteam/fix-x",
        "display_title": "fix",
        "html_url": "u",
    }
    runner = FakeCommandRunner(CommandResult(0, _runs_json(run), ""))
    result = GitHubActions(runner, "o/r").latest_run_for_branch("devteam/fix-x")
    assert result is not None and result.id == 9 and result.is_success
    args = runner.calls[0][0]
    assert any("branch=devteam%2Ffix-x" in arg for arg in args)  # branch URL-encoded in the query


def test_latest_run_for_branch_is_none_when_no_runs() -> None:
    runner = FakeCommandRunner(CommandResult(0, _runs_json(), ""))
    assert GitHubActions(runner, "o/r").latest_run_for_branch("nope") is None


def test_open_pull_requests_parses_the_bare_array_and_derives_the_chain_key() -> None:
    body = json.dumps(
        [
            {"number": 7, "head": {"ref": "devteam/fix-a"}, "title": "A", "html_url": "u7"},
            {"number": 9, "head": {"ref": "devteam/fix-b"}, "title": "B", "html_url": "u9"},
        ]
    )
    runner = FakeCommandRunner(CommandResult(0, body, ""))
    pulls = GitHubActions(runner, "o/r").open_pull_requests()
    assert pulls == [
        PullRequest(7, "devteam/fix-a", "A", "u7"),
        PullRequest(9, "devteam/fix-b", "B", "u9"),
    ]
    assert pulls[0].correlation_ref == "pr-7"  # the stable chain key the monitor advances under
    args = runner.calls[0][0]
    assert any("/pulls?state=open" in arg for arg in args)  # only open PRs are watched


def test_open_pull_requests_is_empty_when_none_are_open() -> None:
    runner = FakeCommandRunner(CommandResult(0, json.dumps([]), ""))
    assert GitHubActions(runner, "o/r").open_pull_requests() == []


def test_a_failed_curl_raises_github_error() -> None:
    runner = FakeCommandRunner(CommandResult(7, "", "curl: (7) Failed to connect"))
    with pytest.raises(GitHubError):
        GitHubActions(runner, "o/r").list_runs()


def test_an_unparseable_response_raises_github_error() -> None:
    runner = FakeCommandRunner(CommandResult(0, "<html>rate limited</html>", ""))
    with pytest.raises(GitHubError):
        GitHubActions(runner, "o/r").list_runs()


def test_a_non_run_payload_degrades_to_no_runs() -> None:
    # A 404/rate-limit body is valid JSON but has no workflow_runs — treat as "nothing found".
    runner = FakeCommandRunner(CommandResult(0, json.dumps({"message": "Not Found"}), ""))
    assert GitHubActions(runner, "o/r").list_runs() == []


def _jobs_json(*jobs: dict[str, object]) -> str:
    return json.dumps({"total_count": len(jobs), "jobs": list(jobs)})


_PASS_JOB: dict[str, object] = {
    "id": 100,
    "name": "javascript",
    "conclusion": "success",
    "steps": [{"number": 1, "name": "Set up job", "conclusion": "success"}],
}
_FAIL_JOB: dict[str, object] = {
    "id": 200,
    "name": "python",
    "conclusion": "failure",
    "steps": [
        {"number": 5, "name": "Run pnpm install", "conclusion": "success"},
        {"number": 6, "name": "Run uv run mypy .", "conclusion": "failure"},
    ],
}


def test_find_failing_step_from_the_public_jobs_api() -> None:
    runner = FakeCommandRunner(CommandResult(0, _jobs_json(_PASS_JOB, _FAIL_JOB), ""))
    step = GitHubActions(runner, "o/r").find_failing_step(29042070113)
    assert step == FailingStep(
        job_id=200, job_name="python", step_name="Run uv run mypy .", step_number=6
    )


def test_find_failing_step_is_none_when_all_green() -> None:
    runner = FakeCommandRunner(CommandResult(0, _jobs_json(_PASS_JOB), ""))
    assert GitHubActions(runner, "o/r").find_failing_step(1) is None


def test_download_job_log_sends_the_token_via_stdin_not_argv() -> None:
    log_line = "2024-01-01T00:00:00Z src/x.py:3: error: boom\n"
    runner = FakeCommandRunner(CommandResult(0, log_line, ""))
    log = GitHubActions(runner, "o/r", token="secret-tok").download_job_log(200)
    assert "src/x.py:3: error: boom" in log
    (args, _cwd, stdin) = runner.calls[0]
    assert "secret-tok" not in " ".join(args)  # the token never appears in argv
    assert stdin is not None
    assert "Authorization: Bearer secret-tok" in stdin  # it rides the curl --config on stdin
    assert "actions/jobs/200/logs" in stdin  # targeting the failing job's log endpoint


def test_download_job_log_without_a_token_raises() -> None:
    runner = FakeCommandRunner(CommandResult(0, "log", ""))
    with pytest.raises(GitHubError):
        GitHubActions(runner, "o/r").download_job_log(200)


def test_download_job_log_surfaces_the_github_error_message() -> None:
    runner = FakeCommandRunner(CommandResult(0, json.dumps({"message": "Bad credentials"}), ""))
    with pytest.raises(GitHubError, match="Bad credentials"):
        GitHubActions(runner, "o/r", token="bad").download_job_log(200)
