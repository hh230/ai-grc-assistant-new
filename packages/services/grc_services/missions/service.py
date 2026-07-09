"""Application service (facade) for the Mission capability.

Groups the mission use cases behind one injectable service. Wiring (which concrete UoW,
dispatcher, and authorization to use) happens in the composition root / infrastructure.
"""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import MissionDTO, MissionSummaryDTO
from .handlers import (
    ApproveGateHandler,
    CancelMissionHandler,
    CompleteMissionHandler,
    CompleteStepHandler,
    CreateMissionHandler,
    GetMissionHandler,
    ListMissionsForWorkspaceHandler,
    PlanMissionHandler,
    RejectGateHandler,
    RequestStepApprovalHandler,
    StartMissionHandler,
    StartStepHandler,
)


class MissionApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def create(self, command: c.CreateMission, ctx: ExecutionContext) -> MissionDTO:
        handler = CreateMissionHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def plan(self, command: c.PlanMission, ctx: ExecutionContext) -> MissionDTO:
        handler = PlanMissionHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def start(self, command: c.StartMission, ctx: ExecutionContext) -> MissionDTO:
        handler = StartMissionHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def start_step(self, command: c.StartStep, ctx: ExecutionContext) -> MissionDTO:
        handler = StartStepHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def request_approval(
        self, command: c.RequestStepApproval, ctx: ExecutionContext
    ) -> MissionDTO:
        handler = RequestStepApprovalHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def approve_gate(self, command: c.ApproveGate, ctx: ExecutionContext) -> MissionDTO:
        handler = ApproveGateHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def reject_gate(self, command: c.RejectGate, ctx: ExecutionContext) -> MissionDTO:
        handler = RejectGateHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def complete_step(self, command: c.CompleteStep, ctx: ExecutionContext) -> MissionDTO:
        handler = CompleteStepHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def complete(self, command: c.CompleteMission, ctx: ExecutionContext) -> MissionDTO:
        handler = CompleteMissionHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def cancel(self, command: c.CancelMission, ctx: ExecutionContext) -> MissionDTO:
        handler = CancelMissionHandler(self._uow, self._events, self._authz)
        return await handler.handle(command, ctx)

    async def get(self, query: q.GetMission, ctx: ExecutionContext) -> MissionDTO:
        handler = GetMissionHandler(self._uow, self._authz)
        return await handler.handle(query, ctx)

    async def list_for_workspace(
        self, query: q.ListMissionsForWorkspace, ctx: ExecutionContext
    ) -> list[MissionSummaryDTO]:
        handler = ListMissionsForWorkspaceHandler(self._uow, self._authz)
        return await handler.handle(query, ctx)
