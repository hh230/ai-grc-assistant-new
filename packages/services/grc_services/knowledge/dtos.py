"""DTOs for the Knowledge capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.knowledge.entities import KnowledgeSource

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class KnowledgeSourceDTO(DataTransferObject):
    id: str
    organization_id: str
    title: str
    source_type: str
    ingestion_status: str
    classification: str
    language: str | None
    is_retrievable: bool

    @classmethod
    def from_domain(cls, s: KnowledgeSource) -> KnowledgeSourceDTO:
        return cls(
            id=str(s.id),
            organization_id=str(s.organization_id),
            title=s.title,
            source_type=s.source_type.value,
            ingestion_status=s.ingestion_status.value,
            classification=s.classification.value,
            language=s.language,
            is_retrievable=s.is_retrievable,
        )
