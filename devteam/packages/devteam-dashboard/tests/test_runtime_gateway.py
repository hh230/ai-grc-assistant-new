"""RuntimeGateway is the one seam to the runtime — assert it re-derives a PR's gated mission and
drives approve/reject through the EXISTING ApprovalGateway, exactly like operate.py, with a fake
GitHub + fake git runner (no network, no real repo). The diff the operator sees is the diff landed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _fakes import FakeGit, FakeGitHub, seed_source
from devteam_dashboard.actions_log import ActionsLog
from devteam_dashboard.runtime_gateway import RuntimeGateway
from devteam_github import PullRequest, WorkflowRun
from devteam_runtime import ApprovalError
from mission_engine.adapters import InMemoryMissionStore


def _gateway(tmp_path: Path, github: FakeGitHub | None = None) -> RuntimeGateway:
    return RuntimeGateway(
        github=github or FakeGitHub(),  # type: ignore[arg-type]
        store=InMemoryMissionStore(),
        git_runner=FakeGit(),
        repo_root=tmp_path,
        repo="o/r",
        actions_log=ActionsLog(tmp_path / "actions.jsonl"),
    )


def test_open_prs_marks_a_failing_pr_actionable(tmp_path: Path) -> None:
    rows = _gateway(tmp_path).open_prs()
    assert len(rows) == 1
    assert rows[0].pr_number == 1
    assert rows[0].ci_status == "failing"
    assert rows[0].actionable is True


def test_open_prs_green_is_not_actionable(tmp_path: Path) -> None:
    green = WorkflowRun(9, "CI", "completed", "success", "pr-1", "ok", "u")
    rows = _gateway(tmp_path, FakeGitHub(run=green)).open_prs()
    assert rows[0].ci_status == "green"
    assert rows[0].actionable is False


def test_materialize_rederives_diagnosis_and_diff(tmp_path: Path) -> None:
    seed_source(tmp_path)
    view = _gateway(tmp_path).materialize(1)
    assert view.state == "awaiting_approval"
    assert view.mission_id
    assert view.mission_status == "awaiting_approval"
    assert view.category  # the analyzer recognized the failure
    assert view.confidence is not None
    assert view.diff is not None and "@@" in view.diff
    assert view.findings and "x.py" in view.findings[0].file


def test_materialize_unknown_pr_is_not_found(tmp_path: Path) -> None:
    view = _gateway(tmp_path).materialize(999)
    assert view.state == "not_found"


def test_materialize_then_approve_lands_via_the_existing_gateway(tmp_path: Path) -> None:
    seed_source(tmp_path)
    gateway = _gateway(tmp_path)
    view = gateway.materialize(1)  # opens the mission in the gateway's own store

    result = gateway.approve(view.mission_id or "", pr_number=1)

    assert result.action == "approved"
    assert result.status == "completed"  # the ApprovalGateway resumed apply→…→open_pr
    # the dashboard's own audit recorded the decision (source for the Approved metric)
    assert ActionsLog(tmp_path / "actions.jsonl").counts().approved == 1


def test_materialize_then_reject_cancels_without_landing(tmp_path: Path) -> None:
    seed_source(tmp_path)
    gateway = _gateway(tmp_path)
    view = gateway.materialize(1)

    result = gateway.reject(view.mission_id or "", pr_number=1)

    assert result.status == "cancelled"
    assert ActionsLog(tmp_path / "actions.jsonl").counts().rejected == 1


def test_approve_unknown_mission_raises_approval_error(tmp_path: Path) -> None:
    with pytest.raises(ApprovalError):
        _gateway(tmp_path).approve("does-not-exist")


def test_materialize_no_open_run_is_observational(tmp_path: Path) -> None:
    # An open PR on a branch with no run yet → nothing to decide.
    github = FakeGitHub(pulls=[PullRequest(2, "other", "wip", "u")])
    view = _gateway(tmp_path, github).materialize(2)
    assert view.state == "no_run"
