"""Use cases for the Knowledge capability (KnowledgeSource identity and facets — see
CLAUDE.md's Framework Engine for the two-library scope model). Content, locator and
ingestion lifecycle live on the separate KnowledgeSourceVersion aggregate, which has no
service layer yet.
"""

from __future__ import annotations

from grc_domain.knowledge.entities import KnowledgeSource
from grc_domain.knowledge.value_objects import KnowledgeScope, LocalizedText
from grc_domain.shared.identifiers import KnowledgeSourceId

from ..shared.authorization import Action, ResourceType
from ..shared.context import ExecutionContext
from ..shared.exceptions import ResourceNotFoundError
from ..shared.handlers import QueryHandler, TransactionalCommandHandler
from ..shared.unit_of_work import UnitOfWork
from .commands import RegisterKnowledgeSource
from .dtos import KnowledgeSourceDTO
from .queries import GetKnowledgeSource, ListKnowledgeSources


class RegisterKnowledgeSourceHandler(
    TransactionalCommandHandler[RegisterKnowledgeSource, KnowledgeSourceDTO]
):
    async def _execute(
        self, command: RegisterKnowledgeSource, context: ExecutionContext, uow: UnitOfWork
    ) -> KnowledgeSourceDTO:
        await self._authz.ensure_can(context, Action.CREATE, ResourceType.KNOWLEDGE_SOURCE)
        scope = (
            KnowledgeScope.for_organization(command.organization_id)
            if command.organization_id is not None
            else KnowledgeScope.global_()
        )
        source = KnowledgeSource.register(
            id=KnowledgeSourceId.generate(),
            scope=scope,
            short_code=command.short_code,
            title=LocalizedText(entries=command.title),
            authority=command.authority,
            jurisdiction=command.jurisdiction,
            knowledge_domain=command.knowledge_domain,
            document_type=command.document_type,
            classification=command.classification,
            tags=command.tags,
            canonical_languages=command.canonical_languages,
        )
        await uow.knowledge_sources.add(source)
        return KnowledgeSourceDTO.from_domain(source)


class GetKnowledgeSourceHandler(QueryHandler[GetKnowledgeSource, KnowledgeSourceDTO]):
    async def handle(
        self, query: GetKnowledgeSource, context: ExecutionContext
    ) -> KnowledgeSourceDTO:
        await self._authz.ensure_can(
            context, Action.READ, ResourceType.KNOWLEDGE_SOURCE, str(query.source_id)
        )
        async with self._uow as uow:
            s = await uow.knowledge_sources.get(context.organization_id, query.source_id)
        if s is None:
            raise ResourceNotFoundError(f"KnowledgeSource {query.source_id} not found")
        return KnowledgeSourceDTO.from_domain(s)


class ListKnowledgeSourcesHandler(QueryHandler[ListKnowledgeSources, list[KnowledgeSourceDTO]]):
    async def handle(
        self, query: ListKnowledgeSources, context: ExecutionContext
    ) -> list[KnowledgeSourceDTO]:
        await self._authz.ensure_can(context, Action.READ, ResourceType.KNOWLEDGE_SOURCE)
        async with self._uow as uow:
            items = await uow.knowledge_sources.list_for_organization(context.organization_id)
        return [KnowledgeSourceDTO.from_domain(s) for s in items]
