"""Admin-controllable worker settings (Knowledge Intelligence KI-P5, ADR-0029) — the seam
that lets an Admin Control Center change the learning cadence, pause/resume the worker, and
request an out-of-cycle run, without this pure package knowing anything about HTTP, RBAC, or
Postgres. ``AutonomousKnowledgeWorker`` asks the injected ``WorkerControlPort`` for the
*current* settings on every ``tick`` rather than trusting the fixed
``LearningCycleScheduler.interval`` it was constructed with, so an admin's change takes
effect on the very next poll — no restart required.

Structurally matched, the same anti-coupling idiom every other port in this package already
uses: the real implementation (a Postgres-backed ``WorkerControlRepository``) is injected and
never imported here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class WorkerControlSettings:
    """The admin-controllable knobs, read fresh at the start of every ``tick``."""

    enabled: bool
    interval: timedelta
    manual_trigger_requested: bool


class WorkerControlPort(Protocol):
    """Structural port a concrete control-state store satisfies without this package
    importing it."""

    async def get_settings(self) -> WorkerControlSettings: ...

    async def clear_manual_trigger(self) -> None:
        """Called once a manually-triggered cycle has run, so the next tick's
        ``get_settings()`` no longer reports a pending manual trigger."""
        ...
