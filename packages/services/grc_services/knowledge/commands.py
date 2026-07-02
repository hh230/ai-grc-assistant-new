"""Commands for the Knowledge capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.knowledge.enums import KnowledgeSourceType
from grc_domain.shared.enums import DataClassification
from grc_domain.shared.identifiers import KnowledgeSourceId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class RegisterKnowledgeSource(Command):
    title: str
    source_type: KnowledgeSourceType
    uri: str
    language: str | None = None
    classification: DataClassification = DataClassification.CONFIDENTIAL


@dataclass(frozen=True, kw_only=True)
class BeginIngestion(Command):
    source_id: KnowledgeSourceId


@dataclass(frozen=True, kw_only=True)
class MarkIngestionIndexed(Command):
    source_id: KnowledgeSourceId


@dataclass(frozen=True, kw_only=True)
class MarkIngestionFailed(Command):
    source_id: KnowledgeSourceId
    reason: str
