"""Domain events for the Knowledge Extraction bounded context.

Immutable, past-tense facts recorded by the ExtractionRun aggregate. Infrastructure relays
them via the transactional outbox; the domain never publishes anything itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..knowledge import KnowledgeScope
from ..shared.events import DomainEvent
from ..shared.identifiers import ExtractionRunId, KnowledgeSourceVersionId
from .enums import ExtractionStage


@dataclass(frozen=True, kw_only=True)
class ExtractionRunOpened(DomainEvent):
    run_id: ExtractionRunId
    scope: KnowledgeScope
    version_id: KnowledgeSourceVersionId


@dataclass(frozen=True, kw_only=True)
class ExtractionRunStarted(DomainEvent):
    run_id: ExtractionRunId


@dataclass(frozen=True, kw_only=True)
class ExtractionStageStarted(DomainEvent):
    run_id: ExtractionRunId
    stage: ExtractionStage


@dataclass(frozen=True, kw_only=True)
class ExtractionStageCompleted(DomainEvent):
    run_id: ExtractionRunId
    stage: ExtractionStage


@dataclass(frozen=True, kw_only=True)
class ExtractionStageFailed(DomainEvent):
    run_id: ExtractionRunId
    stage: ExtractionStage
    reason: str


@dataclass(frozen=True, kw_only=True)
class ExtractionRunAwaitingReview(DomainEvent):
    run_id: ExtractionRunId


@dataclass(frozen=True, kw_only=True)
class ExtractionRunResumed(DomainEvent):
    run_id: ExtractionRunId


@dataclass(frozen=True, kw_only=True)
class ExtractionRunCompleted(DomainEvent):
    run_id: ExtractionRunId


@dataclass(frozen=True, kw_only=True)
class ExtractionRunFailed(DomainEvent):
    run_id: ExtractionRunId
    reason: str


@dataclass(frozen=True, kw_only=True)
class ExtractionRunCancelled(DomainEvent):
    run_id: ExtractionRunId


@dataclass(frozen=True, kw_only=True)
class ExtractionRunSuperseded(DomainEvent):
    run_id: ExtractionRunId
    superseded_by_run_id: ExtractionRunId
