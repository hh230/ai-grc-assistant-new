"""``LearningCycleScheduler`` — the deterministic "is it time to check for knowledge gaps
again" decision. Kept deliberately separate from
``grc_knowledge_intelligence.gap_detection``'s own per-question staleness check
(``DEFAULT_MAX_AGE_DAYS``): that answers "is *this answer* stale and due for a fresh look",
this answers "has enough time passed since the worker last ran a discovery cycle at all" — the
cadence of the outer loop, not the freshness of any one item inside it. No LLM, no I/O: a pure
function of an interval, the last run time, and the clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class LearningCycleScheduler:
    """A fixed-interval cadence: due immediately if the worker has never run, otherwise due
    once ``interval`` has elapsed since ``last_run_at``."""

    interval: timedelta

    def __post_init__(self) -> None:
        if self.interval <= timedelta(0):
            raise ValueError("LearningCycleScheduler.interval must be a positive duration")

    def is_due(self, *, last_run_at: datetime | None, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("is_due(now=...) must be timezone-aware")
        if last_run_at is None:
            return True
        if last_run_at.tzinfo is None:
            raise ValueError("is_due(last_run_at=...) must be timezone-aware")
        return (now - last_run_at) >= self.interval

    def next_run_at(self, *, last_run_at: datetime | None) -> datetime | None:
        """The next time a cycle becomes due. ``None`` means due immediately — the worker has
        never run before."""
        if last_run_at is None:
            return None
        return last_run_at + self.interval
