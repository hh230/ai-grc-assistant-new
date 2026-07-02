"""Command and query handlers (use cases) for the Mission capability.

Each command handler authorizes the action, loads the aggregate within the tenant, invokes
domain behavior, persists, and returns a DTO. The transaction boundary and event dispatch
are owned by `TransactionalCommandHandler`.
"""

from __future__ import annotations

from grc_domain.missions.entities import Mission, MissionStep
from grc_domain.missions.value_objects import MissionGoal, ProposedAction
from grc_domain.shared.identifiers import ApprovalGateId, MissionId, MissionStepId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import (
    ApproveGate,
    CancelMission,
    CompleteMission,
    CompleteStep,
    CreateMission,
    PlanMission,
    RejectGate,
    RequestStepApproval,
    StartMission,
    StartStep,
)
from .dtos import MissionDTO, MissionSummaryDTO
from .queries import GetMission, ListMissionsForWorkspace


async def _load(uow: UnitOfWork, context: ExecutionContext, mission_id: MissionId) -> Mission:
    mission = await uow.missions.get(context.organization_id, mission_id)
    if mission is None:
        raise ResourceNotFoundError(f"Mission {mission_id} not found")
    return mission


class CreateMissionHandler(TransactionalCommandHandler[CreateMission, MissionDTO]):
    async def _execute(
        self, command: CreateMission, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.MISSION)
        mission = Mission.create(
            id=MissionId.generate(),
            organization_id=context.organization_id,
            workspace_id=command.workspace_id,
            goal=MissionGoal(command.goal),
            created_by=context.user_id,
            owner_id=command.owner_id or context.user_id,
        )
        await uow.missions.add(mission)
        return MissionDTO.from_domain(mission)


class PlanMissionHandler(TransactionalCommandHandler[PlanMission, MissionDTO]):
    async def _execute(
        self, command: PlanMission, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        steps = [
            MissionStep(
                id=MissionStepId.generate(),
                name=spec.name,
                side_effect=spec.side_effect,
                agent_id=spec.agent_id,
                tool_ids=spec.tool_ids,
            )
            for spec in command.steps
        ]
        mission.plan(steps)
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class StartMissionHandler(TransactionalCommandHandler[StartMission, MissionDTO]):
    async def _execute(
        self, command: StartMission, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.EXECUTE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        mission.start()
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class StartStepHandler(TransactionalCommandHandler[StartStep, MissionDTO]):
    async def _execute(
        self, command: StartStep, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.EXECUTE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        mission.start_step(command.step_id)
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class RequestStepApprovalHandler(TransactionalCommandHandler[RequestStepApproval, MissionDTO]):
    async def _execute(
        self, command: RequestStepApproval, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.EXECUTE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        mission.request_approval(
            step_id=command.step_id,
            gate_id=ApprovalGateId.generate(),
            proposed_action=ProposedAction(command.action_description),
        )
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class ApproveGateHandler(TransactionalCommandHandler[ApproveGate, MissionDTO]):
    async def _execute(
        self, command: ApproveGate, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.APPROVE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        mission.approve_gate(gate_id=command.gate_id, approver_id=context.user_id)
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class RejectGateHandler(TransactionalCommandHandler[RejectGate, MissionDTO]):
    async def _execute(
        self, command: RejectGate, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.APPROVE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        mission.reject_gate(
            gate_id=command.gate_id, approver_id=context.user_id, reason=command.reason
        )
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class CompleteStepHandler(TransactionalCommandHandler[CompleteStep, MissionDTO]):
    async def _execute(
        self, command: CompleteStep, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.EXECUTE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        mission.complete_step(command.step_id, output_ref=command.output_ref)
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class CompleteMissionHandler(TransactionalCommandHandler[CompleteMission, MissionDTO]):
    async def _execute(
        self, command: CompleteMission, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.EXECUTE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        mission.complete()
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class CancelMissionHandler(TransactionalCommandHandler[CancelMission, MissionDTO]):
    async def _execute(
        self, command: CancelMission, context: ExecutionContext, uow: UnitOfWork
    ) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.MISSION, str(command.mission_id)
        )
        mission = await _load(uow, context, command.mission_id)
        mission.cancel()
        await uow.missions.save(mission)
        return MissionDTO.from_domain(mission)


class GetMissionHandler(QueryHandler[GetMission, MissionDTO]):
    async def handle(self, query: GetMission, context: ExecutionContext) -> MissionDTO:
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.MISSION, str(query.mission_id)
        )
        async with self._uow as uow:
            mission = await uow.missions.get(context.organization_id, query.mission_id)
        if mission is None:
            raise ResourceNotFoundError(f"Mission {query.mission_id} not found")
        return MissionDTO.from_domain(mission)


class ListMissionsForWorkspaceHandler(
    QueryHandler[ListMissionsForWorkspace, list[MissionSummaryDTO]]
):
    async def handle(
        self, query: ListMissionsForWorkspace, context: ExecutionContext
    ) -> list[MissionSummaryDTO]:
        await self._authz.ensure_can(context, Action.READ, ResourceType.MISSION)
        async with self._uow as uow:
            missions = await uow.missions.list_for_workspace(
                context.organization_id, query.workspace_id
            )
        return [MissionSummaryDTO.from_domain(m) for m in missions]
