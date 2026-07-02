"""Application service for the Control capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import ControlDTO
from .handlers import (
    CreateControlHandler,
    GetControlHandler,
    LinkControlEvidenceHandler,
    ListControlsForWorkspaceHandler,
    MapControlToFrameworkHandler,
    SetControlImplementationStatusHandler,
)


class ControlApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def create(self, command: c.CreateControl, ctx: ExecutionContext) -> ControlDTO:
        return await CreateControlHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def map_to_framework(
        self, command: c.MapControlToFramework, ctx: ExecutionContext
    ) -> ControlDTO:
        return await MapControlToFrameworkHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def link_evidence(
        self, command: c.LinkControlEvidence, ctx: ExecutionContext
    ) -> ControlDTO:
        return await LinkControlEvidenceHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def set_implementation_status(
        self, command: c.SetControlImplementationStatus, ctx: ExecutionContext
    ) -> ControlDTO:
        return await SetControlImplementationStatusHandler(
            self._uow, self._events, self._authz
        ).handle(command, ctx)

    async def get(self, query: q.GetControl, ctx: ExecutionContext) -> ControlDTO:
        return await GetControlHandler(self._uow, self._authz).handle(query, ctx)

    async def list_for_workspace(
        self, query: q.ListControlsForWorkspace, ctx: ExecutionContext
    ) -> list[ControlDTO]:
        return await ListControlsForWorkspaceHandler(self._uow, self._authz).handle(query, ctx)
