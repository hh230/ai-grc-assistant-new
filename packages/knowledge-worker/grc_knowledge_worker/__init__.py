"""grc_knowledge_worker — the Autonomous Learning Loop (Knowledge Intelligence KI-P4,
ADR-0028): merges KI-P1's curated question catalog with KI-P3's ontology-generated questions,
a deterministic learning-cycle scheduler, and the ``AutonomousKnowledgeWorker``
runner/orchestrator that repeats gap research over the combined set. See README.md.
"""

from __future__ import annotations

from .question_sources import combine_question_sources
from .scheduler import LearningCycleScheduler
from .worker import (
    AutonomousKnowledgeWorker,
    CycleOutcome,
    GapResearchOutcomeLike,
    GapResearchRunnerPort,
)

__all__ = [
    "AutonomousKnowledgeWorker",
    "CycleOutcome",
    "GapResearchOutcomeLike",
    "GapResearchRunnerPort",
    "LearningCycleScheduler",
    "combine_question_sources",
]
