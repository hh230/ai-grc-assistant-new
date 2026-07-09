"""Use cases for the Control capability."""

from __future__ import annotations

from grc_domain.controls.entities import Control
from grc_domain.frameworks.value_objects import FrameworkControlRef
from grc_domain.shared.identifiers import ControlId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import (
    CreateControl,
    LinkControlEvidence,
    MapControlToFramework,
    SetControlImplementationStatus,
)
from .dtos import ControlDTO
from .queries import GetControl, ListControlsForWorkspace


async def _load(uow: UnitOfWork, ctx: ExecutionContext, control_id: ControlId) -> Control:
    control = await uow.controls.get(ctx.organization_id, control_id)
    if control is None:
        raise ResourceNotFoundError(f"Control {control_id} not found")
    return control


class CreateControlHandler(TransactionalCommandHandler[CreateControl, ControlDTO]):
    async def _execute(
        self, command: CreateControl, context: ExecutionContext, uow: UnitOfWork
    ) -> ControlDTO:
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.CONTROL)
        control = Control.create(
            id=ControlId.generate(),
            organization_id=context.organization_id,
            workspace_id=command.workspace_id,
            title=command.title,
            description=command.description,
            owner_id=context.user_id,
        )
        await uow.controls.add(control)
        return ControlDTO.from_domain(control)


class MapControlToFrameworkHandler(TransactionalCommandHandler[MapControlToFramework, ControlDTO]):
    async def _execute(
        self, command: MapControlToFramework, context: ExecutionContext, uow: UnitOfWork
    ) -> ControlDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.CONTROL, str(command.control_id)
        )
        control = await _load(uow, context, command.control_id)
        control.map_to_framework_control(
            FrameworkControlRef(
                framework_id=command.framework_id,
                framework_control_id=command.framework_control_id,
            )
        )
        await uow.controls.save(control)
        return ControlDTO.from_domain(control)


class LinkControlEvidenceHandler(TransactionalCommandHandler[LinkControlEvidence, ControlDTO]):
    async def _execute(
        self, command: LinkControlEvidence, context: ExecutionContext, uow: UnitOfWork
    ) -> ControlDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.CONTROL, str(command.control_id)
        )
        control = await _load(uow, context, command.control_id)
        control.link_evidence(command.evidence_id)
        await uow.controls.save(control)
        return ControlDTO.from_domain(control)


class SetControlImplementationStatusHandler(
    TransactionalCommandHandler[SetControlImplementationStatus, ControlDTO]
):
    async def _execute(
        self, command: SetControlImplementationStatus, context: ExecutionContext, uow: UnitOfWork
    ) -> ControlDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.CONTROL, str(command.control_id)
        )
        control = await _load(uow, context, command.control_id)
        control.set_implementation_status(command.status)
        await uow.controls.save(control)
        return ControlDTO.from_domain(control)


class GetControlHandler(QueryHandler[GetControl, ControlDTO]):
    async def handle(
        self, query: GetControl, context: ExecutionContext
    ) -> ControlDTO:
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.CONTROL, str(query.control_id)
        )
        async with self._uow as uow:
            control = await uow.controls.get(context.organization_id, query.control_id)
        if control is None:
            raise ResourceNotFoundError(f"Control {query.control_id} not found")
        return ControlDTO.from_domain(control)


class ListControlsForWorkspaceHandler(QueryHandler[ListControlsForWorkspace, list[ControlDTO]]):
    async def handle(
        self, query: ListControlsForWorkspace, context: ExecutionContext
    ) -> list[ControlDTO]:
        await self._authz.ensure_can(context, Action.READ, ResourceType.CONTROL)
        async with self._uow as uow:
            items = await uow.controls.list_for_workspace(
                context.organization_id, query.workspace_id
            )
        return [ControlDTO.from_domain(c) for c in items]
