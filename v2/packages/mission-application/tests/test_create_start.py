"""S7 acceptance for the write side — Create + Start (unit level, ports faked).

Create is a standalone command (define → create → project); Start reuses the `MissionCommand`
template (load → validate → invoke → project). Faking the ports proves each command's *policy* — the
definition is used, the creation is projected with the product `type`/`scope`, an already-started
mission is rejected — without the engine or the catalog (those are exercised end-to-end in grc-api).
"""

from __future__ import annotations

from typing import Any

import pytest
from mission_application import (
    CreatedMission,
    CreateMissionCommand,
    CreateMissionInputs,
    IllegalCommand,
    StartInputs,
    StartMissionCommand,
)
from mission_application.contracts import CommandContext


def _context(tenant_id: str = "T") -> CommandContext:
    return CommandContext(tenant_id=tenant_id, principal_id="u", roles=("practitioner",))


class _Status:
    def __init__(self, value: str) -> None:
        self.value = value


class _FakeMission:
    def __init__(self, mission_id: str, status: str, *, pending: bool = False) -> None:
        self.id = mission_id
        self._status = status
        self.has_active_approval = pending
        self.tenant_id = "T"

    @property
    def status(self) -> _Status:
        return _Status(self._status)


class _RecordingProjection:
    def __init__(self) -> None:
        self.projected: list[Any] = []

    def project(self, subject: Any) -> None:
        self.projected.append(subject)


# --- Create -----------------------------------------------------------------------------


class _FakeStep:
    def __init__(self, *, consequential: bool = False) -> None:
        self.consequential = consequential


class _FakePlan:
    def __init__(self, steps: tuple[_FakeStep, ...]) -> None:
        self.steps = steps


class _FakeDefiner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def define(self, mission_type: str, scope: str, tenant: Any) -> tuple[str, Any]:
        self.calls.append((mission_type, scope))
        # a 3-step plan with one human gate (the second step is consequential)
        plan = _FakePlan((_FakeStep(), _FakeStep(consequential=True), _FakeStep()))
        return (f"{mission_type}: {scope}", plan)


class _FakeCreator:
    def __init__(self) -> None:
        self.created: list[tuple[str, str]] = []

    def create(self, goal: str, plan: Any, tenant: Any, *, idempotency_key: str = "") -> Any:
        self.created.append((goal, idempotency_key))
        return _FakeMission("mis_new", "planned")


def test_create_defines_creates_projects_and_summarises_the_plan() -> None:
    definer, creator, projection = _FakeDefiner(), _FakeCreator(), _RecordingProjection()
    command = CreateMissionCommand(definer=definer, creator=creator, projection=projection)

    inputs = CreateMissionInputs(
        mission_type="gap_assessment", scope="Vendor Acme", idempotency_key="k1"
    )
    result = command.execute(_context(), inputs)

    # defined from the product type + scope; created idempotently from the definition
    assert definer.calls == [("gap_assessment", "Vendor Acme")]
    assert creator.created == [("gap_assessment: Vendor Acme", "k1")]
    # projected as a creation carrying the product metadata the Core does not store
    assert len(projection.projected) == 1
    created = projection.projected[0]
    assert isinstance(created, CreatedMission)
    assert created.mission_type == "gap_assessment" and created.scope == "Vendor Acme"
    # the outcome carries the plan summary for the review station
    assert result.mission_id == "mis_new" and result.status == "planned"
    assert result.steps == 3 and result.human_approvals == 1


# --- Start ------------------------------------------------------------------------------


class _FakeAccess:
    def __init__(self, mission: _FakeMission | None) -> None:
        self._mission = mission

    def load_for_update(self, tenant_id: str, mission_id: str) -> Any | None:
        return self._mission


class _FakeWorkflow:
    def __init__(self) -> None:
        self.started: list[str] = []

    def start(self, mission: Any) -> None:
        self.started.append(mission.id)

    def approve_step(self, mission: Any, **_: Any) -> None: ...
    def reject_step(self, mission: Any, **_: Any) -> None: ...


def test_start_drives_the_workflow_for_a_planned_mission() -> None:
    workflow, projection = _FakeWorkflow(), _RecordingProjection()
    command = StartMissionCommand(
        access=_FakeAccess(_FakeMission("mis_1", "planned")),
        projection=projection,
        workflow=workflow,
    )

    result = command.execute(_context(), "mis_1", StartInputs())

    assert workflow.started == ["mis_1"]
    assert len(projection.projected) == 1  # the template projects after the transition
    assert result.mission_id == "mis_1"


def test_start_rejects_an_already_started_mission() -> None:
    workflow = _FakeWorkflow()
    command = StartMissionCommand(
        access=_FakeAccess(_FakeMission("mis_1", "executing")),
        projection=_RecordingProjection(),
        workflow=workflow,
    )
    with pytest.raises(IllegalCommand):
        command.execute(_context(), "mis_1", StartInputs())
    assert workflow.started == []  # never invoked
