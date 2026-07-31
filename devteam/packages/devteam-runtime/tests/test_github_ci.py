"""The wiring: a (fake) CI failure -> real-shaped logs -> the Developer's diff -> the approval gate.

Deterministic — the GitHub connector is driven by a fake CommandRunner returning canned jobs JSON
then a canned mypy log, so no network. Proves the full engineering spine: find the failing step ->
download the log -> parse the real mypy errors -> the Developer proposes a real diff -> pause at the
gate. The live entrypoint does the same with real curl + GITHUB_TOKEN against a real repo.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from devteam_github import GitHubActions
from devteam_runtime.github_ci import open_mission_for_run_failure
from devteam_tools import CommandResult
from mission_engine.lifecycle import MissionStatus


class FakeRunner:
    """Pops queued CommandResults in call order and records (args, stdin) — no real curl or git."""

    def __init__(self, results: Sequence[CommandResult] | None = None) -> None:
        self._results = list(results or [])
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def run(self, args: Sequence[str], *, cwd: Path, stdin: str | None = None) -> CommandResult:
        self.calls.append((tuple(args), stdin))
        return self._results.pop(0) if self._results else CommandResult(0, "", "")


_JOBS = json.dumps(
    {
        "jobs": [
            {"id": 100, "name": "javascript", "conclusion": "success", "steps": []},
            {
                "id": 200,
                "name": "python",
                "conclusion": "failure",
                "steps": [{"number": 6, "name": "Run uv run mypy .", "conclusion": "failure"}],
            },
        ]
    }
)
_LOG = "2024-01-01T00:00:01Z src/x.py:3: error: Missing return type  [no-untyped-def]\n"


def test_real_log_failure_opens_a_gated_mission_with_a_real_diff(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def f():\n    pass\n    return None\n")  # line 3
    github = GitHubActions(
        FakeRunner([CommandResult(0, _JOBS, ""), CommandResult(0, _LOG, "")]), "o/r", token="t"
    )
    git = FakeRunner()
    mission = open_mission_for_run_failure(github, 42, repo_root=tmp_path, git_runner=git)

    assert mission is not None
    assert mission.status is MissionStatus.AWAITING_APPROVAL  # paused at the human gate
    assert len(mission.step_results) == 1  # only the Developer ran
    assert not git.calls  # nothing touched the repo before approval
    # the Developer proposed a REAL diff from the parsed mypy error (rides the output, ADR 0051)
    output = mission.step_results[0].output
    assert "```diff" in output
    assert "type: ignore[no-untyped-def]" in output


def test_no_failing_step_opens_no_mission(tmp_path: Path) -> None:
    all_green = json.dumps({"jobs": [{"id": 1, "name": "x", "conclusion": "success", "steps": []}]})
    github = GitHubActions(FakeRunner([CommandResult(0, all_green, "")]), "o/r", token="t")
    mission = open_mission_for_run_failure(github, 1, repo_root=tmp_path, git_runner=FakeRunner())
    assert mission is None
