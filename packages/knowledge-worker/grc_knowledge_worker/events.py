"""Worker activity events (Knowledge Intelligence KI-P5, ADR-0029) — the operational,
audit-safe vocabulary an ``AutonomousKnowledgeWorker`` cycle reports through an injected
sink, for a human-facing activity timeline. Deliberately not a chain-of-thought log: every
``message`` is a short, structured statement of *what happened* (a cycle started, a gap was
detected, a source was searched, an item was saved, an error occurred) — never a model's raw
reasoning text (CLAUDE.md §19 "no raw chain-of-thought to end users").

Pure and I/O-free like every other type in this package: recording is delegated to an
injected ``WorkerEventSink``, structurally matched (the same anti-coupling idiom
``GapResearchRunnerPort`` already uses) so this package never imports a database driver.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol


class WorkerEventType(str, Enum):
    CYCLE_STARTED = "cycle_started"
    QUESTIONS_LOADED = "questions_loaded"
    GAP_DETECTED = "gap_detected"
    SOURCE_SEARCHED = "source_searched"
    KNOWLEDGE_DISCOVERED = "knowledge_discovered"
    ITEM_SAVED = "item_saved"
    ERROR = "error"
    CYCLE_COMPLETED = "cycle_completed"


@dataclass(frozen=True, kw_only=True)
class WorkerEvent:
    """One line of the activity timeline. ``metadata`` carries small, already-public
    structured facts (a domain, a source name, a confidence score) — never a prompt, a raw
    LLM completion, or anything a human reviewer could mistake for hidden reasoning."""

    event_type: WorkerEventType
    message: str
    occurred_at: datetime
    question_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


class WorkerEventSink(Protocol):
    """Structural port a concrete recorder (e.g. a Postgres-backed
    ``WorkerEventRepository``) satisfies without this package importing it."""

    async def record(self, event: WorkerEvent) -> None: ...
