"""grc_regulation_ingestion — the Saudi Regulations Ingestion Pipeline's pure orchestrator
(Knowledge Intelligence KI-P6, ADR-0030). Reuses grc_knowledge_worker's
LearningCycleScheduler/WorkerControlPort/WorkerEventSink directly rather than reimplementing a
parallel worker vocabulary. See README.md.
"""

from __future__ import annotations

from .models import RegulationCatalogEntry
from .worker import (
    AutonomousRegulationIngestionWorker,
    CatalogSourcePort,
    CycleOutcome,
    RegulationFetchRunnerPort,
    RegulationOutcomeLike,
)

__all__ = [
    "AutonomousRegulationIngestionWorker",
    "CatalogSourcePort",
    "CycleOutcome",
    "RegulationCatalogEntry",
    "RegulationFetchRunnerPort",
    "RegulationOutcomeLike",
]
