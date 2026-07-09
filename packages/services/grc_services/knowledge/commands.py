"""Commands for the Knowledge capability."""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.knowledge.enums import DocumentType, KnowledgeDomain
from grc_domain.shared.enums import DataClassification
from grc_domain.shared.identifiers import OrganizationId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class RegisterKnowledgeSource(Command):
    """Register a KnowledgeSource. ``organization_id`` is ``None`` for a GLOBAL-scoped
    source (shared platform-wide); set it to isolate the source to that one tenant."""

    organization_id: OrganizationId | None
    short_code: str
    title: tuple[tuple[str, str], ...]
    authority: str
    jurisdiction: str
    knowledge_domain: KnowledgeDomain
    document_type: DocumentType
    classification: DataClassification = DataClassification.CONFIDENTIAL
    tags: tuple[str, ...] = field(default_factory=tuple)
    canonical_languages: tuple[str, ...] = field(default_factory=tuple)
