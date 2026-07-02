"""Use cases for the Knowledge capability (domain state of RAG sources; no embedding here)."""

from __future__ import annotations

from grc_domain.knowledge.entities import KnowledgeSource
from grc_domain.knowledge.value_objects import SourceLocator
from grc_domain.shared.identifiers import KnowledgeSourceId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import (
    BeginIngestion,
    MarkIngestionFailed,
    MarkIngestionIndexed,
    RegisterKnowledgeSource,
)
from .dtos import KnowledgeSourceDTO
from .queries import GetKnowledgeSource, ListKnowledgeSources


async def _load(
    uow: UnitOfWork, ctx: ExecutionContext, source_id: KnowledgeSourceId
) -> KnowledgeSource:
    s = await uow.knowledge_sources.get(ctx.organization_id, source_id)
    if s is None:
        raise ResourceNotFoundError(f"KnowledgeSource {source_id} not found")
    return s


class RegisterKnowledgeSourceHandler(
    TransactionalCommandHandler[RegisterKnowledgeSource, KnowledgeSourceDTO]
):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.KNOWLEDGE_SOURCE)
        source = KnowledgeSource.register(
            id=KnowledgeSourceId.generate(),
            organization_id=context.organization_id,
            title=command.title,
            source_type=command.source_type,
            locator=SourceLocator(command.uri),
            language=command.language,
            classification=command.classification,
        )
        await uow.knowledge_sources.add(source)
        return KnowledgeSourceDTO.from_domain(source)


class BeginIngestionHandler(TransactionalCommandHandler[BeginIngestion, KnowledgeSourceDTO]):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.KNOWLEDGE_SOURCE, str(command.source_id)
        )
        source = await _load(uow, context, command.source_id)
        source.begin_ingestion()
        await uow.knowledge_sources.save(source)
        return KnowledgeSourceDTO.from_domain(source)


class MarkIngestionIndexedHandler(
    TransactionalCommandHandler[MarkIngestionIndexed, KnowledgeSourceDTO]
):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.KNOWLEDGE_SOURCE, str(command.source_id)
        )
        source = await _load(uow, context, command.source_id)
        source.mark_indexed()
        await uow.knowledge_sources.save(source)
        return KnowledgeSourceDTO.from_domain(source)


class MarkIngestionFailedHandler(
    TransactionalCommandHandler[MarkIngestionFailed, KnowledgeSourceDTO]
):
    async def _execute(self, command, context, uow):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.UPDATE, ResourceType.KNOWLEDGE_SOURCE, str(command.source_id)
        )
        source = await _load(uow, context, command.source_id)
        source.mark_failed(reason=command.reason)
        await uow.knowledge_sources.save(source)
        return KnowledgeSourceDTO.from_domain(source)


class GetKnowledgeSourceHandler(QueryHandler[GetKnowledgeSource, KnowledgeSourceDTO]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.KNOWLEDGE_SOURCE, str(query.source_id)
        )
        async with self._uow as uow:
            s = await uow.knowledge_sources.get(context.organization_id, query.source_id)
        if s is None:
            raise ResourceNotFoundError(f"KnowledgeSource {query.source_id} not found")
        return KnowledgeSourceDTO.from_domain(s)


class ListKnowledgeSourcesHandler(QueryHandler[ListKnowledgeSources, list[KnowledgeSourceDTO]]):
    async def handle(self, query, context):  # type: ignore[override]
        await self._authz.ensure_can(context, Action.READ, ResourceType.KNOWLEDGE_SOURCE)
        async with self._uow as uow:
            items = await uow.knowledge_sources.list_for_organization(context.organization_id)
        return [KnowledgeSourceDTO.from_domain(s) for s in items]
