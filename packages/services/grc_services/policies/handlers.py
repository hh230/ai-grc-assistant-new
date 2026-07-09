"""Use cases for the Policy capability (authoring lifecycle with human approval)."""

from __future__ import annotations

from grc_domain.policies.entities import Policy
from grc_domain.policies.value_objects import PolicyBody
from grc_domain.shared.identifiers import PolicyId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import (
    ApprovePolicy,
    DraftPolicy,
    PublishPolicy,
    RetirePolicy,
    SubmitPolicyForReview,
)
from .dtos import PolicyDTO
from .queries import GetPolicy, ListPolicies


async def _load(uow: UnitOfWork, ctx: ExecutionContext, policy_id: PolicyId) -> Policy:
    policy = await uow.policies.get(ctx.organization_id, policy_id)
    if policy is None:
        raise ResourceNotFoundError(f"Policy {policy_id} not found")
    return policy


class DraftPolicyHandler(TransactionalCommandHandler[DraftPolicy, PolicyDTO]):
    async def _execute(
        self, command: DraftPolicy, context: ExecutionContext, uow: UnitOfWork
    ) -> PolicyDTO:
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.POLICY)
        policy = Policy.draft(
            id=PolicyId.generate(),
            organization_id=context.organization_id,
            title=command.title,
            body=PolicyBody(command.body_text),
            owner_id=context.user_id,
        )
        await uow.policies.add(policy)
        return PolicyDTO.from_domain(policy)


class SubmitPolicyForReviewHandler(TransactionalCommandHandler[SubmitPolicyForReview, PolicyDTO]):
    async def _execute(
        self, command: SubmitPolicyForReview, context: ExecutionContext, uow: UnitOfWork
    ) -> PolicyDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.POLICY, str(command.policy_id)
        )
        policy = await _load(uow, context, command.policy_id)
        policy.submit_for_review()
        await uow.policies.save(policy)
        return PolicyDTO.from_domain(policy)


class ApprovePolicyHandler(TransactionalCommandHandler[ApprovePolicy, PolicyDTO]):
    async def _execute(
        self, command: ApprovePolicy, context: ExecutionContext, uow: UnitOfWork
    ) -> PolicyDTO:
        await self._authz.ensure_can(
            context, Action.APPROVE, ResourceType.POLICY, str(command.policy_id)
        )
        policy = await _load(uow, context, command.policy_id)
        policy.approve(approver_id=context.user_id)
        await uow.policies.save(policy)
        return PolicyDTO.from_domain(policy)


class PublishPolicyHandler(TransactionalCommandHandler[PublishPolicy, PolicyDTO]):
    async def _execute(
        self, command: PublishPolicy, context: ExecutionContext, uow: UnitOfWork
    ) -> PolicyDTO:
        await self._authz.ensure_can(
            context, Action.PUBLISH, ResourceType.POLICY, str(command.policy_id)
        )
        policy = await _load(uow, context, command.policy_id)
        policy.publish()
        await uow.policies.save(policy)
        return PolicyDTO.from_domain(policy)


class RetirePolicyHandler(TransactionalCommandHandler[RetirePolicy, PolicyDTO]):
    async def _execute(
        self, command: RetirePolicy, context: ExecutionContext, uow: UnitOfWork
    ) -> PolicyDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.POLICY, str(command.policy_id)
        )
        policy = await _load(uow, context, command.policy_id)
        policy.retire()
        await uow.policies.save(policy)
        return PolicyDTO.from_domain(policy)


class GetPolicyHandler(QueryHandler[GetPolicy, PolicyDTO]):
    async def handle(
        self, query: GetPolicy, context: ExecutionContext
    ) -> PolicyDTO:
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.POLICY, str(query.policy_id)
        )
        async with self._uow as uow:
            policy = await uow.policies.get(context.organization_id, query.policy_id)
        if policy is None:
            raise ResourceNotFoundError(f"Policy {query.policy_id} not found")
        return PolicyDTO.from_domain(policy)


class ListPoliciesHandler(QueryHandler[ListPolicies, list[PolicyDTO]]):
    async def handle(
        self, query: ListPolicies, context: ExecutionContext
    ) -> list[PolicyDTO]:
        await self._authz.ensure_can(context, Action.READ, ResourceType.POLICY)
        async with self._uow as uow:
            items = await uow.policies.list_for_organization(context.organization_id)
        return [PolicyDTO.from_domain(p) for p in items]
