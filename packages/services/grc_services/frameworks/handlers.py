"""Use cases for the Framework capability.

Frameworks are platform-level reference data (not tenant-scoped), so these handlers do not
filter by organization; authorization still applies.
"""

from __future__ import annotations

from grc_domain.frameworks.entities import Framework
from grc_domain.frameworks.value_objects import FrameworkVersion

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import DeprecateFramework, ImportFramework, PublishFramework
from .dtos import FrameworkDTO
from .queries import GetFramework, ListPublishedFrameworks


class ImportFrameworkHandler(TransactionalCommandHandler[ImportFramework, FrameworkDTO]):
    async def _execute(
        self, command: ImportFramework, context: ExecutionContext, uow: UnitOfWork
    ) -> FrameworkDTO:
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.FRAMEWORK)
        framework = Framework.import_definition(
            id=command.framework_id,
            name=command.name,
            version=FrameworkVersion(command.version),
            controls=command.controls,
            region=command.region,
            languages=command.languages,
        )
        await uow.frameworks.add(framework)
        return FrameworkDTO.from_domain(framework)


class PublishFrameworkHandler(TransactionalCommandHandler[PublishFramework, FrameworkDTO]):
    async def _execute(
        self, command: PublishFramework, context: ExecutionContext, uow: UnitOfWork
    ) -> FrameworkDTO:
        await self._authz.ensure_can(
            context, Action.PUBLISH, ResourceType.FRAMEWORK, str(command.framework_id)
        )
        framework = await uow.frameworks.get(
            command.framework_id, FrameworkVersion(command.version)
        )
        if framework is None:
            raise ResourceNotFoundError(f"Framework {command.framework_id} not found")
        framework.publish()
        await uow.frameworks.save(framework)
        return FrameworkDTO.from_domain(framework)


class DeprecateFrameworkHandler(TransactionalCommandHandler[DeprecateFramework, FrameworkDTO]):
    async def _execute(
        self, command: DeprecateFramework, context: ExecutionContext, uow: UnitOfWork
    ) -> FrameworkDTO:
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.FRAMEWORK, str(command.framework_id)
        )
        framework = await uow.frameworks.get(
            command.framework_id, FrameworkVersion(command.version)
        )
        if framework is None:
            raise ResourceNotFoundError(f"Framework {command.framework_id} not found")
        framework.deprecate()
        await uow.frameworks.save(framework)
        return FrameworkDTO.from_domain(framework)


class GetFrameworkHandler(QueryHandler[GetFramework, FrameworkDTO]):
    async def handle(
        self, query: GetFramework, context: ExecutionContext
    ) -> FrameworkDTO:
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.FRAMEWORK, str(query.framework_id)
        )
        async with self._uow as uow:
            framework = await uow.frameworks.get(
                query.framework_id, FrameworkVersion(query.version)
            )
        if framework is None:
            raise ResourceNotFoundError(f"Framework {query.framework_id} not found")
        return FrameworkDTO.from_domain(framework)


class ListPublishedFrameworksHandler(QueryHandler[ListPublishedFrameworks, list[FrameworkDTO]]):
    async def handle(
        self, query: ListPublishedFrameworks, context: ExecutionContext
    ) -> list[FrameworkDTO]:
        await self._authz.ensure_can(context, Action.READ, ResourceType.FRAMEWORK)
        async with self._uow as uow:
            items = await uow.frameworks.list_published()
        return [FrameworkDTO.from_domain(f) for f in items]
