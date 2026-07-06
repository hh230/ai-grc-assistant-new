"""grc_knowledge_worker — the Autonomous Learning Loop (Knowledge Intelligence KI-P4,
ADR-0028): merges KI-P1's curated question catalog with KI-P3's ontology-generated questions,
a deterministic learning-cycle scheduler, and the ``AutonomousKnowledgeWorker``
runner/orchestrator that repeats gap research over the combined set. KI-P5 (ADR-0029) adds
the optional ``WorkerControlPort``/``WorkerEventSink`` seams an Admin AI Worker Control
Center uses to pause/resume, reschedule, manually trigger, and observe the loop. See
README.md.
"""

from __future__ import annotations

from .control import WorkerControlPort, WorkerControlSettings
from .events import WorkerEvent, WorkerEventSink, WorkerEventType
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
    "WorkerControlPort",
    "WorkerControlSettings",
    "WorkerEvent",
    "WorkerEventSink",
    "WorkerEventType",
    "combine_question_sources",
]
