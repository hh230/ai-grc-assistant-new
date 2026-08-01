"""The three S2 commands on the frozen `MissionCommand` base — authorize/validate/invoke behaviour,
verified with fakes (no Core, no HTTP). Proves ADR 0054's language sufficed: no contract changed."""

from __future__ import annotations

from typing import Any

import pytest
from mission_application import (
    ApproveInputs,
    ApproveMissionStepCommand,
    CommandContext,
    IllegalCommand,
    NotAuthorized,
    RejectInputs,
    RejectMissionStepCommand,
)
from mission_engine import ApprovalRequest, Mission, Plan, PlanStep
from pipeline_contracts import TenantContext

TENANT = TenantContext(tenant_id="T", principal_id="u")


def _ctx(*roles: str) -> CommandContext:
    return CommandContext(tenant_id="T", principal_id="bob@t", roles=tuple(roles))


class _Access:
    def __init__(self, mission: Mission) -> None:
        self._mission = mission

    def load_for_update(self, tenant_id: str, mission_id: str) -> Any | None:
        return self._mission if mission_id == self._mission.id else None


class _Projection:
    def __init__(self) -> None:
        self.projected: list[object] = []

    def project(self, subject: object) -> None:
        self.projected.append(subject)


class _Workflow:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def approve_step(self, mission: Any, *, step_id: str, approver: Any, comment: str = "") -> None:
        self.calls.append(("approve", step_id))

    def reject_step(self, mission: Any, *, step_id: str, approver: Any, comment: str = "") -> None:
        self.calls.append(("reject", step_id))


def _awaiting() -> Mission:
    m = Mission.create(goal="g", tenant=TENANT)
    m.set_plan(Plan(steps=(PlanStep(description="Compare", instruction="x"),)))
    m.begin_execution()
    m.await_approval(ApprovalRequest(reason="publish", requested_by="a"))
    return m


def _failed() -> Mission:
    m = Mission.create(goal="g", tenant=TENANT)
    m.set_plan(Plan(steps=(PlanStep(description="Do", instruction="x"),)))
    m.begin_execution()
    m.fail("boom")
    return m


# --- approve ----------------------------------------------------------------------------


def test_approve_drives_workflow_and_projects() -> None:
    mission = _awaiting()
    workflow = _Workflow()
    projection = _Projection()
    command = ApproveMissionStepCommand(
        access=_Access(mission), projection=projection, workflow=workflow
    )
    result = command.execute(_ctx("approver"), mission.id, ApproveInputs(step_id="s1"))
    assert workflow.calls == [("approve", "s1")]
    assert projection.projected == [mission]
    assert result.mission_id == mission.id


def test_approve_requires_approver_role() -> None:
    mission = _awaiting()
    command = ApproveMissionStepCommand(
        access=_Access(mission), projection=_Projection(), workflow=_Workflow()
    )
    with pytest.raises(NotAuthorized):
        command.execute(_ctx("practitioner"), mission.id, ApproveInputs(step_id="s1"))


def test_approve_rejects_when_not_awaiting() -> None:
    mission = _failed()  # not awaiting approval
    command = ApproveMissionStepCommand(
        access=_Access(mission), projection=_Projection(), workflow=_Workflow()
    )
    with pytest.raises(IllegalCommand):
        command.execute(_ctx("approver"), mission.id, ApproveInputs(step_id="s1"))


# --- reject -----------------------------------------------------------------------------


def test_reject_drives_workflow() -> None:
    mission = _awaiting()
    workflow = _Workflow()
    command = RejectMissionStepCommand(
        access=_Access(mission), projection=_Projection(), workflow=workflow
    )
    command.execute(_ctx("approver"), mission.id, RejectInputs(step_id="s1", comment="no"))
    assert workflow.calls == [("reject", "s1")]


def test_reject_requires_approver_role() -> None:
    mission = _awaiting()
    command = RejectMissionStepCommand(
        access=_Access(mission), projection=_Projection(), workflow=_Workflow()
    )
    with pytest.raises(NotAuthorized):
        command.execute(_ctx(), mission.id, RejectInputs(step_id="s1"))
