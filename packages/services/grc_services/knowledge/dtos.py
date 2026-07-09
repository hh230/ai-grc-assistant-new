"""DTOs for the Knowledge capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.knowledge.entities import KnowledgeSource

from ..shared.messages import DataTransferObject


@dataclass(frozen=True)
class KnowledgeSourceDTO(DataTransferObject):
    id: str
    scope_kind: str
    organization_id: str | None
    short_code: str
    title: tuple[tuple[str, str], ...]
    authority: str
    jurisdiction: str
    knowledge_domain: str
    document_type: str
    classification: str
    tags: tuple[str, ...]
    canonical_languages: tuple[str, ...]
    current_version_id: str | None

    @classmethod
    def from_domain(cls, s: KnowledgeSource) -> KnowledgeSourceDTO:
        return cls(
            id=str(s.id),
            scope_kind=s.scope.kind.value,
            organization_id=(
                str(s.scope.organization_id) if s.scope.organization_id is not None else None
            ),
            short_code=s.short_code,
            title=s.title.entries,
            authority=s.authority,
            jurisdiction=s.jurisdiction,
            knowledge_domain=s.knowledge_domain.value,
            document_type=s.document_type.value,
            classification=s.classification.value,
            tags=s.tags,
            canonical_languages=s.canonical_languages,
            current_version_id=(
                str(s.current_version_id) if s.current_version_id is not None else None
            ),
        )
