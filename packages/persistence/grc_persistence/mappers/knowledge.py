"""Mapper for the Knowledge (RAG source) context."""

from __future__ import annotations

from grc_domain.knowledge.entities import KnowledgeSource
from grc_domain.knowledge.enums import DocumentType, KnowledgeDomain, KnowledgeScopeKind
from grc_domain.knowledge.value_objects import KnowledgeScope
from grc_domain.shared.enums import DataClassification
from grc_domain.shared.identifiers import (
    FrameworkId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
    OrganizationId,
)

from ..contracts.mapper import AggregateMapper
from ..models.knowledge import KnowledgeSourceModel
from ._common import (
    aware,
    decode_actor,
    decode_localized_text,
    encode_actor,
    encode_localized_text,
)


def _encode_scope(scope: KnowledgeScope) -> tuple[str, str | None]:
    organization_id = scope.organization_id
    return scope.kind.value, str(organization_id) if organization_id is not None else None


def _decode_scope(scope_kind: str, scope_organization_id: str | None) -> KnowledgeScope:
    if KnowledgeScopeKind(scope_kind) is KnowledgeScopeKind.GLOBAL:
        return KnowledgeScope.global_()
    assert scope_organization_id is not None, "organization scope requires scope_organization_id"
    return KnowledgeScope.for_organization(OrganizationId(scope_organization_id))


class KnowledgeSourceMapper(AggregateMapper[KnowledgeSource, KnowledgeSourceModel]):
    def to_orm(self, aggregate: KnowledgeSource) -> KnowledgeSourceModel:
        scope_kind, scope_organization_id = _encode_scope(aggregate.scope)
        return KnowledgeSourceModel(
            id=str(aggregate.id),
            scope_kind=scope_kind,
            scope_organization_id=scope_organization_id,
            short_code=aggregate.short_code,
            title=encode_localized_text(aggregate.title),
            authority=aggregate.authority,
            jurisdiction=aggregate.jurisdiction,
            knowledge_domain=aggregate.knowledge_domain.value,
            document_type=aggregate.document_type.value,
            classification=aggregate.classification.value,
            framework_refs=[str(ref) for ref in aggregate.framework_refs],
            tags=list(aggregate.tags),
            canonical_languages=list(aggregate.canonical_languages),
            steward=encode_actor(aggregate.steward) if aggregate.steward is not None else None,
            current_version_id=(
                str(aggregate.current_version_id)
                if aggregate.current_version_id is not None
                else None
            ),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: KnowledgeSourceModel, aggregate: KnowledgeSource) -> None:
        scope_kind, scope_organization_id = _encode_scope(aggregate.scope)
        model.scope_kind = scope_kind
        model.scope_organization_id = scope_organization_id
        model.short_code = aggregate.short_code
        model.title = encode_localized_text(aggregate.title)
        model.authority = aggregate.authority
        model.jurisdiction = aggregate.jurisdiction
        model.knowledge_domain = aggregate.knowledge_domain.value
        model.document_type = aggregate.document_type.value
        model.classification = aggregate.classification.value
        model.framework_refs = [str(ref) for ref in aggregate.framework_refs]
        model.tags = list(aggregate.tags)
        model.canonical_languages = list(aggregate.canonical_languages)
        model.steward = encode_actor(aggregate.steward) if aggregate.steward is not None else None
        model.current_version_id = (
            str(aggregate.current_version_id) if aggregate.current_version_id is not None else None
        )
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: KnowledgeSourceModel) -> KnowledgeSource:
        return KnowledgeSource(
            id=KnowledgeSourceId(model.id),
            scope=_decode_scope(model.scope_kind, model.scope_organization_id),
            short_code=model.short_code,
            title=decode_localized_text(model.title),
            authority=model.authority,
            jurisdiction=model.jurisdiction,
            knowledge_domain=KnowledgeDomain(model.knowledge_domain),
            document_type=DocumentType(model.document_type),
            classification=DataClassification(model.classification),
            framework_refs=tuple(FrameworkId(ref) for ref in model.framework_refs),
            tags=tuple(model.tags),
            canonical_languages=tuple(model.canonical_languages),
            steward=decode_actor(model.steward) if model.steward is not None else None,
            current_version_id=(
                KnowledgeSourceVersionId(model.current_version_id)
                if model.current_version_id is not None
                else None
            ),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


knowledge_source_mapper = KnowledgeSourceMapper()
