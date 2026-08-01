"""The `MissionCommand` Template Method (ADR 0054): fixed sequence, MissionAccess load, projection,
typed failures — verified with fakes (no Core, no HTTP)."""

from __future__ import annotations

from typing import Any

import pytest
from mission_application import (
    CommandContext,
    MissionCommand,
    MissionNotFound,
    NotAuthorized,
)
from mission_engine import Mission
from pipeline_contracts import TenantContext


def _ctx(roles: tuple[str, ...] = ("approver",)) -> CommandContext:
    return CommandContext(tenant_id="T", principal_id="bob@t", roles=roles)


class _FakeAccess:
    def __init__(self, mission: Mission | None) -> None:
        self._mission = mission
        self.calls: list[tuple[str, str]] = []

    def load_for_update(self, tenant_id: str, mission_id: str) -> Any | None:
        self.calls.append((tenant_id, mission_id))
        return self._mission


class _SpyProjection:
    def __init__(self) -> None:
        self.projected: list[object] = []

    def project(self, subject: object) -> None:
        self.projected.append(subject)


class _RecordingCommand(MissionCommand[str]):
    """A concrete command that only records the order its hooks fire in."""

    def __init__(self, *, access: Any, projection: Any) -> None:
        super().__init__(access=access, projection=projection)
        self.order: list[str] = []

    def authorize(self, context: CommandContext, inputs: str) -> None:
        self.order.append("authorize")
        if not context.has_role("approver"):
            raise NotAuthorized("approver role required")

    def validate(self, context: CommandContext, mission: Any, inputs: str) -> None:
        self.order.append("validate")

    def invoke(self, context: CommandContext, mission: Any, inputs: str) -> None:
        self.order.append("invoke")


def _mission() -> Mission:
    return Mission.create(goal="g", tenant=TenantContext(tenant_id="T", principal_id="u"))


def test_runs_the_fixed_sequence_and_returns_a_command_result() -> None:
    mission = _mission()
    access = _FakeAccess(mission)
    projection = _SpyProjection()
    command = _RecordingCommand(access=access, projection=projection)

    result = command.execute(_ctx(), mission.id, "inputs")

    assert command.order == ["authorize", "validate", "invoke"]
    assert access.calls == [("T", mission.id)]  # loaded via MissionAccess, scoped by tenant_id
    assert projection.projected == [mission]  # projected on success
    assert result.mission_id == mission.id
    assert result.status == "created"
    assert result.approval_pending is False


def test_missing_mission_raises_mission_not_found() -> None:
    command = _RecordingCommand(access=_FakeAccess(None), projection=_SpyProjection())
    with pytest.raises(MissionNotFound):
        command.execute(_ctx(), "nope", "inputs")


def test_unauthorized_short_circuits_before_load() -> None:
    access = _FakeAccess(_mission())
    projection = _SpyProjection()
    command = _RecordingCommand(access=access, projection=projection)
    with pytest.raises(NotAuthorized):
        command.execute(_ctx(roles=("practitioner",)), "m1", "inputs")
    assert access.calls == []  # never loaded
    assert projection.projected == []  # never projected
    assert command.order == ["authorize"]
