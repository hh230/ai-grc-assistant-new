"""`RejectMissionStepCommand` — a human rejects the mission's pending gate, fail-safe (ADR 0044).

Same shape as approve: **Authorize** Approver role · **Validate** a gate is pending · **Invoke**
drive the rejection through the `MissionWorkflow` (the Core stops the mission fail-safe; the action
never runs). The base handles load / project / result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mission_application.commands.base import MissionCommand
from mission_application.contracts import (
    CommandContext,
    IllegalCommand,
    MissionAccess,
    MissionWorkflow,
    NotAuthorized,
    ProjectionPort,
)

APPROVER_ROLE = "approver"


@dataclass(frozen=True)
class RejectInputs:
    step_id: str
    comment: str = ""


class RejectMissionStepCommand(MissionCommand[RejectInputs]):
    def __init__(
        self,
        *,
        access: MissionAccess,
        projection: ProjectionPort[Any],
        workflow: MissionWorkflow,
    ) -> None:
        super().__init__(access=access, projection=projection)
        self._workflow = workflow

    def authorize(self, context: CommandContext, inputs: RejectInputs) -> None:
        if not context.has_role(APPROVER_ROLE):
            raise NotAuthorized("rejecting a gate requires the Approver role")

    def validate(self, context: CommandContext, mission: Any, inputs: RejectInputs) -> None:
        if not mission.has_active_approval:
            raise IllegalCommand("the mission is not awaiting approval")

    def invoke(self, context: CommandContext, mission: Any, inputs: RejectInputs) -> None:
        self._workflow.reject_step(
            mission,
            step_id=inputs.step_id,
            approver=context.tenant_context(),
            comment=inputs.comment,
        )
