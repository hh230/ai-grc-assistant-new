"""`ApproveMissionStepCommand` — a human approves the mission's pending gate (ADR 0044, ADR 0054).

Fills only the policy hooks of `MissionCommand`; the sequence (load → project → result) is the
base's. **Authorize:** the caller must hold the **Approver** role. **Validate:** the mission must be
holding a pending gate. **Invoke:** drive the approval through the `MissionWorkflow` (which approves
+ resumes on the Core). Loading, projecting, and the `CommandResult` are the template's.
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
class ApproveInputs:
    step_id: str
    comment: str = ""


class ApproveMissionStepCommand(MissionCommand[ApproveInputs]):
    def __init__(
        self,
        *,
        access: MissionAccess,
        projection: ProjectionPort[Any],
        workflow: MissionWorkflow,
    ) -> None:
        super().__init__(access=access, projection=projection)
        self._workflow = workflow

    def authorize(self, context: CommandContext, inputs: ApproveInputs) -> None:
        if not context.has_role(APPROVER_ROLE):
            raise NotAuthorized("approving a gate requires the Approver role")

    def validate(self, context: CommandContext, mission: Any, inputs: ApproveInputs) -> None:
        if not mission.has_active_approval:
            raise IllegalCommand("the mission is not awaiting approval")

    def invoke(self, context: CommandContext, mission: Any, inputs: ApproveInputs) -> None:
        self._workflow.approve_step(
            mission,
            step_id=inputs.step_id,
            approver=context.tenant_context(),
            comment=inputs.comment,
        )
