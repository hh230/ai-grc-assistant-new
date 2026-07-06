"""``AutonomousKnowledgeWorker`` — the runner/orchestrator this phase (KI-P4) adds: the
missing "Scheduler" and "repeat" links in the requested loop::

    Scheduler -> Ontology -> Question Generator -> Gap Detector -> Research Coordinator ->
    Trusted Sources -> Knowledge Repository -> repeat

Every other link already exists and is reused unmodified. ``combine_question_sources`` (this
package's own ``question_sources`` module) only assembles the question set from KI-P1's
catalog and KI-P3's ontology; gap detection, research coordination, trusted-source lookup, and
storage are exactly ``grc_knowledge_research_adapters.KnowledgeGapResearchRunner`` —
consumed *structurally*, not by import (``GapResearchRunnerPort`` below matches its ``run``
method exactly), the same anti-coupling idiom that runner's own ``KnowledgeItemStore``
protocol already uses for ``grc_persistence_web``. This keeps this package pure and
dependency-free beyond ``grc_knowledge_intelligence``/``grc_knowledge_ontology``: it never
imports the research/adapters/persistence packages, network libraries, or an LLM SDK.

The clock, the sleep function, and the runner are all injected, so a repeatable cycle is
fully unit-testable without real time passing, a real database, or a real LLM call. Real,
always-on process wiring (an ``apps/worker`` entrypoint invoking ``tick`` from an actual
infinite loop with real Postgres/LLM/HTTP adapters and OS signal handling) is a deployment
composition-root concern layered on top of this module, not built into it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from grc_knowledge_intelligence import KnowledgeQuestion

from .scheduler import LearningCycleScheduler


class GapResearchOutcomeLike(Protocol):
    """The shape of one researched question's result the worker reports on — satisfied
    structurally by ``grc_knowledge_research_adapters.GapResearchOutcome`` without this
    package importing it. Declared as read-only properties (not plain attributes) because
    the real ``GapResearchOutcome`` is a frozen dataclass — mypy only accepts a frozen
    (read-only) field as matching a Protocol member declared the same way."""

    @property
    def question_id(self) -> str: ...

    @property
    def stored(self) -> bool: ...


class GapResearchRunnerPort(Protocol):
    """Matches ``grc_knowledge_research_adapters.KnowledgeGapResearchRunner.run`` exactly, so
    the real runner can be injected directly with no adapter glue."""

    async def run(
        self, questions: tuple[KnowledgeQuestion, ...], *, now: datetime
    ) -> Sequence[GapResearchOutcomeLike]: ...


@dataclass(frozen=True)
class CycleOutcome:
    """What happened on one ``tick``: either the scheduler decided a cycle was not yet due, or
    a full gap-research cycle ran and these are its per-question results."""

    ran: bool
    reason: str
    started_at: datetime
    outcomes: tuple[GapResearchOutcomeLike, ...] = ()

    @property
    def stored_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.stored)


class AutonomousKnowledgeWorker:
    """Ties the scheduler and the already fully-wired gap-research runner together into a
    repeatable learning cycle over a fixed question set.

    One failed ``tick`` (the injected runner itself raising) is not swallowed here —
    ``KnowledgeGapResearchRunner`` already isolates a single question's research/storage
    failure (CLAUDE.md §16, fail-safe); a raise past that point is a genuine defect in the
    injected runner, not a routine "no evidence yet" outcome, and should surface rather than
    be hidden by this loop.
    """

    def __init__(
        self,
        *,
        questions: tuple[KnowledgeQuestion, ...],
        runner: GapResearchRunnerPort,
        scheduler: LearningCycleScheduler,
        last_run_at: datetime | None = None,
    ) -> None:
        self._questions = questions
        self._runner = runner
        self._scheduler = scheduler
        self._last_run_at = last_run_at

    @property
    def last_run_at(self) -> datetime | None:
        return self._last_run_at

    async def tick(self, *, now: datetime) -> CycleOutcome:
        """Run exactly one scheduling decision: skip if not due, otherwise research every
        actionable gap in the combined question set and record ``now`` as the last run."""
        if not self._scheduler.is_due(last_run_at=self._last_run_at, now=now):
            return CycleOutcome(ran=False, reason="not_due", started_at=now)

        outcomes = await self._runner.run(self._questions, now=now)
        self._last_run_at = now
        return CycleOutcome(ran=True, reason="due", started_at=now, outcomes=tuple(outcomes))

    async def run_loop(
        self,
        *,
        clock: Callable[[], datetime],
        sleep: Callable[[float], Awaitable[None]],
        poll_interval_seconds: float,
        max_iterations: int,
    ) -> tuple[CycleOutcome, ...]:
        """Repeats ``tick`` up to ``max_iterations`` times, sleeping ``poll_interval_seconds``
        between checks. Bounded rather than infinite so this stays a deterministic, testable
        unit — a real always-on process is expected to drive ``tick`` itself from its own
        infinite loop (with OS signal handling for graceful shutdown), using this method only
        for bounded runs and tests."""
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")

        results: list[CycleOutcome] = []
        for iteration in range(max_iterations):
            results.append(await self.tick(now=clock()))
            if iteration < max_iterations - 1:
                await sleep(poll_interval_seconds)
        return tuple(results)
