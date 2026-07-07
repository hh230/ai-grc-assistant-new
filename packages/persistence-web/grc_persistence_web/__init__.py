"""grc_persistence_web — adapters against apps/web's live PostgreSQL schema.

The AI runtime (apps/api, apps/worker) has exactly one database: the one apps/web already
owns. This package implements domain/tool ports (e.g. grc_tools.ToolInvocationRecorder)
against that schema; it never introduces a second database or duplicates apps/web's own
migrations.
"""

from __future__ import annotations

from .invocations import PostgresToolInvocationRecorder
from .knowledge import KnowledgeItemRecord, KnowledgeItemRepository
from .missions import MissionRecord, MissionStepRecord, PolicyMissionStore
from .policies import PolicyRecord, PolicyRepository
from .pool import Database, normalize_dsn
from .regulations import (
    NewRegulationSection,
    RegulationDocumentRecord,
    RegulationDocumentRepository,
    RegulationSectionRecord,
    RegulationSectionRepository,
    RegulationSourceRecord,
    RegulationSourceRepository,
    RegulationSourceVersionRecord,
    RegulationSourceVersionRepository,
    SectionEmbeddingCandidate,
)
from .regulatory import (
    RegulatoryObligationRecord,
    RegulatoryObligationRepository,
    RegulatoryRawDocumentRecord,
    RegulatoryRawDocumentRepository,
)
from .worker_control import (
    WorkerControlRecord,
    WorkerControlRepository,
    WorkerEventRecord,
    WorkerEventRepository,
    WorkerRunHistoryRepository,
    WorkerRunRecord,
)

__all__ = [
    "Database",
    "normalize_dsn",
    "PostgresToolInvocationRecorder",
    "PolicyRepository",
    "PolicyRecord",
    "PolicyMissionStore",
    "MissionRecord",
    "MissionStepRecord",
    "RegulatoryRawDocumentRepository",
    "RegulatoryRawDocumentRecord",
    "RegulatoryObligationRepository",
    "RegulatoryObligationRecord",
    "KnowledgeItemRepository",
    "KnowledgeItemRecord",
    "WorkerControlRepository",
    "WorkerControlRecord",
    "WorkerRunHistoryRepository",
    "WorkerRunRecord",
    "WorkerEventRepository",
    "WorkerEventRecord",
    "RegulationSourceRepository",
    "RegulationSourceRecord",
    "RegulationSourceVersionRepository",
    "RegulationSourceVersionRecord",
    "RegulationDocumentRepository",
    "RegulationDocumentRecord",
    "RegulationSectionRepository",
    "RegulationSectionRecord",
    "NewRegulationSection",
    "SectionEmbeddingCandidate",
]
