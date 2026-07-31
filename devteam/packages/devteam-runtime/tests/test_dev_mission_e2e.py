"""End-to-end: a Dev Mission runs on the FROZEN v2 Core, in-memory, no Postgres (ADR 0061 Phase 0).

Proves the architectural bet: dev work is a governed Mission — it walks the frozen lifecycle
(CREATED → PLANNED → EXECUTING → COMPLETED), a Dev Tool executes behind the frozen ExecutionPort,
and the frozen audit terminal records the mission-event stream under tenant:platform.
"""

from __future__ import annotations

from pathlib import Path

from devteam_contracts import PLATFORM_TENANT_ID
from devteam_runtime import DevMissionRuntime
from devteam_tools import CHECK_REPO_HEALTH
from mission_engine.lifecycle import MissionStatus
from mission_engine.plan import PlanStep


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# constitution\n")
    return tmp_path


def test_dev_mission_completes_on_the_frozen_core(tmp_path: Path) -> None:
    runtime = DevMissionRuntime(_repo(tmp_path))
    mission = runtime.run_plan(
        "Phase 0 smoke: check platform repo health",
        (PlanStep(description="repo health", instruction="check", tool=CHECK_REPO_HEALTH),),
    )

    assert mission.status is MissionStatus.COMPLETED
    assert mission.tenant_id == PLATFORM_TENANT_ID
    assert len(mission.step_results) == 1
    assert mission.step_results[0].ok is True
    assert "git=True" in mission.step_results[0].output


def test_audit_records_the_full_mission_event_stream(tmp_path: Path) -> None:
    runtime = DevMissionRuntime(_repo(tmp_path))
    mission = runtime.run_plan(
        "Phase 0 smoke",
        (PlanStep(description="repo health", instruction="check", tool=CHECK_REPO_HEALTH),),
    )

    names = runtime.audit.event_names_for(mission.id)
    assert names == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]


def test_a_missing_tool_fails_the_mission_safe(tmp_path: Path) -> None:
    runtime = DevMissionRuntime(_repo(tmp_path))
    mission = runtime.run_plan(
        "route to a tool that does not exist",
        (PlanStep(description="bad", instruction="x", tool="no_such_tool"),),
    )
    # ADR 0042 §7: an executor failure fails the mission safe, not a crash.
    assert mission.status is MissionStatus.FAILED
