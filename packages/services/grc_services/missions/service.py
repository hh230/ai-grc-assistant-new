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

    def _cmd(self, handler_cls: type) -> object:
        return handler_cls(self._uow, self._events, self._authz)

    def _qry(self, handler_cls: type) -> object:
        return handler_cls(self._uow, self._authz)

    async def create(self, command: c.CreateMission, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(CreateMissionHandler).handle(command, ctx)

    async def plan(self, command: c.PlanMission, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(PlanMissionHandler).handle(command, ctx)

    async def start(self, command: c.StartMission, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(StartMissionHandler).handle(command, ctx)

    async def start_step(self, command: c.StartStep, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(StartStepHandler).handle(command, ctx)

    async def request_approval(
        self, command: c.RequestStepApproval, ctx: ExecutionContext
    ) -> MissionDTO:
        return await self._cmd(RequestStepApprovalHandler).handle(command, ctx)

    async def approve_gate(self, command: c.ApproveGate, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(ApproveGateHandler).handle(command, ctx)

    async def reject_gate(self, command: c.RejectGate, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(RejectGateHandler).handle(command, ctx)

    async def complete_step(self, command: c.CompleteStep, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(CompleteStepHandler).handle(command, ctx)

    async def complete(self, command: c.CompleteMission, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(CompleteMissionHandler).handle(command, ctx)

    async def cancel(self, command: c.CancelMission, ctx: ExecutionContext) -> MissionDTO:
        return await self._cmd(CancelMissionHandler).handle(command, ctx)

    async def get(self, query: q.GetMission, ctx: ExecutionContext) -> MissionDTO:
        return await self._qry(GetMissionHandler).handle(query, ctx)

    async def list_for_workspace(
        self, query: q.ListMissionsForWorkspace, ctx: ExecutionContext
    ) -> list[MissionSummaryDTO]:
        return await self._qry(ListMissionsForWorkspaceHandler).handle(query, ctx)
