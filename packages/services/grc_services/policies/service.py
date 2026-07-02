"""Application service for the Policy capability."""

from __future__ import annotations

from ..shared.authorization import AuthorizationService
from ..shared.context import ExecutionContext
from ..shared.events import EventDispatcher
from ..shared.unit_of_work import UnitOfWork
from . import commands as c
from . import queries as q
from .dtos import PolicyDTO
from .handlers import (
    ApprovePolicyHandler,
    DraftPolicyHandler,
    GetPolicyHandler,
    ListPoliciesHandler,
    PublishPolicyHandler,
    RetirePolicyHandler,
    SubmitPolicyForReviewHandler,
)


class PolicyApplicationService:
    def __init__(
        self, uow: UnitOfWork, events: EventDispatcher, authz: AuthorizationService
    ) -> None:
        self._uow, self._events, self._authz = uow, events, authz

    async def draft(self, command: c.DraftPolicy, ctx: ExecutionContext) -> PolicyDTO:
        return await DraftPolicyHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def submit_for_review(
        self, command: c.SubmitPolicyForReview, ctx: ExecutionContext
    ) -> PolicyDTO:
        return await SubmitPolicyForReviewHandler(self._uow, self._events, self._authz).handle(
            command, ctx
        )

    async def approve(self, command: c.ApprovePolicy, ctx: ExecutionContext) -> PolicyDTO:
        return await ApprovePolicyHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def publish(self, command: c.PublishPolicy, ctx: ExecutionContext) -> PolicyDTO:
        return await PublishPolicyHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def retire(self, command: c.RetirePolicy, ctx: ExecutionContext) -> PolicyDTO:
        return await RetirePolicyHandler(self._uow, self._events, self._authz).handle(command, ctx)

    async def get(self, query: q.GetPolicy, ctx: ExecutionContext) -> PolicyDTO:
        return await GetPolicyHandler(self._uow, self._authz).handle(query, ctx)

    async def list(self, query: q.ListPolicies, ctx: ExecutionContext) -> list[PolicyDTO]:
        return await ListPoliciesHandler(self._uow, self._authz).handle(query, ctx)
