"""`StartMissionCommand` — the user starts a reviewed mission (Slice S7).

The product word is **"Start mission"**; the Core op is `execute` — the two languages stay separate.
It fills only the policy hooks of `MissionCommand`; the sequence (load → project → result) is the
base's, exactly as approve/reject — **the template is reused, not rebuilt.** *Validate:* the mission
must still be pre-run (a "Draft" in product terms — CREATED/PLANNED). *Invoke:* drive the start
through the `MissionWorkflow` (its `start` op → the Core's `execute`).
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
    ProjectionPort,
)

# The pre-run statuses a mission can be started from ("Draft" in product language).
_STARTABLE = frozenset({"created", "planned"})


@dataclass(frozen=True)
class StartInputs:
    """No inputs — starting needs only the mission id (in the URL)."""


class StartMissionCommand(MissionCommand[StartInputs]):
    def __init__(
        self,
        *,
        access: MissionAccess,
        projection: ProjectionPort[Any],
        workflow: MissionWorkflow,
    ) -> None:
        super().__init__(access=access, projection=projection)
        self._workflow = workflow

    def authorize(self, context: CommandContext, inputs: StartInputs) -> None:
        """Practitioner — any authenticated tenant member; tenant scoping is the real guard and role
        enforcement is declared-but-deferred, like the other command guards."""

    def validate(self, context: CommandContext, mission: Any, inputs: StartInputs) -> None:
        if mission.status.value not in _STARTABLE:
            raise IllegalCommand(f"mission {mission.id} has already been started")

    def invoke(self, context: CommandContext, mission: Any, inputs: StartInputs) -> None:
        self._workflow.start(mission)
