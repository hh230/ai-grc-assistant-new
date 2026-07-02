"""Application service for the Assessment capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import AssessmentDTO
from .handlers import (
    CompleteAssessmentHandler,
    GetAssessmentHandler,
    ListAssessmentsHandler,
    PlanAssessmentHandler,
    RecordAssessmentResultHandler,
    StartAssessmentHandler,
)


class AssessmentApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def plan(self, command: c.PlanAssessment, ctx: ExecutionContext) -> AssessmentDTO:
        return await PlanAssessmentHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def start(self, command: c.StartAssessment, ctx: ExecutionContext) -> AssessmentDTO:
        return await StartAssessmentHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def record_result(
        self, command: c.RecordAssessmentResult, ctx: ExecutionContext
    ) -> AssessmentDTO:
        return await RecordAssessmentResultHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def complete(self, command: c.CompleteAssessment, ctx: ExecutionContext) -> AssessmentDTO:
        return await CompleteAssessmentHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def get(self, query: q.GetAssessment, ctx: ExecutionContext) -> AssessmentDTO:
        return await GetAssessmentHandler(self._uow, self._authz).handle(query, ctx)

    async def list(self, query: q.ListAssessments, ctx: ExecutionContext) -> list[AssessmentDTO]:
        return await ListAssessmentsHandler(self._uow, self._authz).handle(query, ctx)
