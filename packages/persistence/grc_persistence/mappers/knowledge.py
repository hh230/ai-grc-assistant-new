"""Mapper for the Knowledge (RAG source) context."""

from __future__ import annotations

from grc_domain.knowledge.entities import KnowledgeSource
from grc_domain.knowledge.enums import IngestionStatus, KnowledgeSourceType
from grc_domain.knowledge.value_objects import Checksum, SourceLocator
from grc_domain.shared.enums import DataClassification
from grc_domain.shared.identifiers import KnowledgeSourceId, OrganizationId

from ..contracts.mapper import AggregateMapper
from ..models.knowledge import KnowledgeSourceModel
from ._common import aware


class KnowledgeSourceMapper(AggregateMapper[KnowledgeSource, KnowledgeSourceModel]):
    def to_orm(self, aggregate: KnowledgeSource) -> KnowledgeSourceModel:
        return KnowledgeSourceModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            title=aggregate.title,
            source_type=aggregate.source_type.value,
            locator_uri=aggregate.locator.uri,
            language=aggregate.language,
            classification=aggregate.classification.value,
            ingestion_status=aggregate.ingestion_status.value,
            checksum_algorithm=(
                aggregate.checksum.algorithm if aggregate.checksum is not None else None
            ),
            checksum_value=aggregate.checksum.value if aggregate.checksum is not None else None,
            failure_reason=aggregate.failure_reason,
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: KnowledgeSourceModel, aggregate: KnowledgeSource) -> None:
        model.title = aggregate.title
        model.source_type = aggregate.source_type.value
        model.locator_uri = aggregate.locator.uri
        model.language = aggregate.language
        model.classification = aggregate.classification.value
        model.ingestion_status = aggregate.ingestion_status.value
        model.checksum_algorithm = (
            aggregate.checksum.algorithm if aggregate.checksum is not None else None
        )
        model.checksum_value = aggregate.checksum.value if aggregate.checksum is not None else None
        model.failure_reason = aggregate.failure_reason
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: KnowledgeSourceModel) -> KnowledgeSource:
        checksum: Checksum | None = None
        if model.checksum_algorithm is not None and model.checksum_value is not None:
            checksum = Checksum(algorithm=model.checksum_algorithm, value=model.checksum_value)
        return KnowledgeSource(
            id=KnowledgeSourceId(model.id),
            organization_id=OrganizationId(model.organization_id),
            title=model.title,
            source_type=KnowledgeSourceType(model.source_type),
            locator=SourceLocator(model.locator_uri),
            language=model.language,
            classification=DataClassification(model.classification),
            ingestion_status=IngestionStatus(model.ingestion_status),
            checksum=checksum,
            failure_reason=model.failure_reason,
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


knowledge_source_mapper = KnowledgeSourceMapper()
