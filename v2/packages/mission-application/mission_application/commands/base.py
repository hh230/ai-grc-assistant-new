"""`MissionCommand` — the Template Method every mission-mutating command follows (ADR 0054).

The use-case sequence is written **once** here, so it is never repeated across the dozens of
commands to come (Approve, Reject, Retry, Cancel, Archive, Replan, Publish, …):

    authorize → load → validate → invoke → project → CommandResult

A subclass fills only the policy hooks (`authorize`, `validate`, `invoke`). It never re-implements
the flow, touches the raw store (it loads through `MissionAccess`), or knows how many projections
live behind `ProjectionPort`. Failure is a typed Application error the hook raises; a result in hand
always means success.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from mission_application.contracts import (
    CommandContext,
    CommandResult,
    MissionAccess,
    MissionNotFound,
    ProjectionPort,
)

Inputs = TypeVar("Inputs")


class MissionCommand(ABC, Generic[Inputs]):
    """Base for a command that mutates one mission. Collaborators are injected (inverted deps): a
    `MissionAccess` to load, a `ProjectionPort` to project. The Core-driving `invoke` hook holds the
    engine the concrete command was given."""

    def __init__(self, *, access: MissionAccess, projection: ProjectionPort[Any]) -> None:
        self._access = access
        self._projection = projection

    def execute(self, context: CommandContext, mission_id: str, inputs: Inputs) -> CommandResult:
        self.authorize(context, inputs)
        mission = self._access.load_for_update(context.tenant_id, mission_id)
        if mission is None:
            # Absent or cross-tenant — existence is not revealed (fail-closed).
            raise MissionNotFound(mission_id)
        self.validate(context, mission, inputs)
        self.invoke(context, mission, inputs)
        self._projection.project(mission)
        return CommandResult(
            mission_id=mission.id,
            status=mission.status.value,
            approval_pending=mission.has_active_approval,
        )

    # --- hooks a subclass fills -----------------------------------------------------------

    @abstractmethod
    def authorize(self, context: CommandContext, inputs: Inputs) -> None:
        """Reject a caller not permitted to run this use case — raise `NotAuthorized`."""

    def validate(self, context: CommandContext, mission: Any, inputs: Inputs) -> None:
        """Optional precondition: raise `IllegalCommand` if invalid in the mission's current state.
        Default no-op — the Core still enforces the domain rule as defence in depth."""

    @abstractmethod
    def invoke(self, context: CommandContext, mission: Any, inputs: Inputs) -> None:
        """Drive the Core (Mission Engine) to perform the transition and persist it."""
