"""Application service for the Evidence capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import EvidenceDTO
from .handlers import (
    CollectEvidenceHandler,
    GetEvidenceHandler,
    LinkEvidenceToControlHandler,
    ListEvidenceForControlHandler,
    RejectEvidenceHandler,
    ValidateEvidenceHandler,
)


class EvidenceApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def collect(self, command: c.CollectEvidence, ctx: ExecutionContext) -> EvidenceDTO:
        return await CollectEvidenceHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def validate(self, command: c.ValidateEvidence, ctx: ExecutionContext) -> EvidenceDTO:
        return await ValidateEvidenceHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def reject(self, command: c.RejectEvidence, ctx: ExecutionContext) -> EvidenceDTO:
        return await RejectEvidenceHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def link_to_control(
        self, command: c.LinkEvidenceToControl, ctx: ExecutionContext
    ) -> EvidenceDTO:
        return await LinkEvidenceToControlHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def get(self, query: q.GetEvidence, ctx: ExecutionContext) -> EvidenceDTO:
        return await GetEvidenceHandler(self._uow, self._authz).handle(query, ctx)

    async def list_for_control(
        self, query: q.ListEvidenceForControl, ctx: ExecutionContext
    ) -> list[EvidenceDTO]:
        return await ListEvidenceForControlHandler(self._uow, self._authz).handle(query, ctx)
