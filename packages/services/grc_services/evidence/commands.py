"""Commands for the Evidence capability."""

from __future__ import annotations

from dataclasses import dataclass

from grc_domain.evidence.enums import EvidenceType
from grc_domain.shared.identifiers import ControlId, EvidenceId, KnowledgeSourceId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class CollectEvidence(Command):
    title: str
    evidence_type: EvidenceType
    knowledge_source_id: KnowledgeSourceId | None = None


@dataclass(frozen=True, kw_only=True)
class ValidateEvidence(Command):
    evidence_id: EvidenceId


@dataclass(frozen=True, kw_only=True)
class RejectEvidence(Command):
    evidence_id: EvidenceId
    reason: str


@dataclass(frozen=True, kw_only=True)
class LinkEvidenceToControl(Command):
    evidence_id: EvidenceId
    control_id: ControlId
