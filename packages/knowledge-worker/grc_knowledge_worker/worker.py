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

KI-P5 (ADR-0029) adds the two seams an Admin AI Worker Control Center needs, both optional
and both structurally-ported like everything else here: a ``WorkerControlPort`` ``tick``
re-reads on every call (so an admin's enable/disable, interval, or manual-trigger change
takes effect on the next poll, not just at process start), and a ``WorkerEventSink`` that
receives a ``cycle_started``/``cycle_completed``/``error`` event around each cycle for a
human-facing activity timeline. Neither seam changes this worker's behaviour when omitted —
every KI-P4 caller and test keeps working unmodified.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from grc_knowledge_intelligence import KnowledgeQuestion

from .control import WorkerControlPort, WorkerControlSettings
from .events import WorkerEvent, WorkerEventSink, WorkerEventType
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

    @property
    def error(self) -> str | None: ...


class GapResearchRunnerPort(Protocol):
    """Matches ``grc_knowledge_research_adapters.KnowledgeGapResearchRunner.run`` exactly, so
    the real runner can be injected directly with no adapter glue."""

    async def run(
        self, questions: tuple[KnowledgeQuestion, ...], *, now: datetime
    ) -> Sequence[GapResearchOutcomeLike]: ...


@dataclass(frozen=True)
class CycleOutcome:
    """What happened on one ``tick``. ``reason`` is one of: ``"disabled"`` (an admin paused
    the worker), ``"not_due"`` (the scheduler says wait), ``"due"`` (a normal scheduled
    cycle ran), or ``"manual"`` (an admin's "Run Learning Now" request ran the cycle early).
    Only ``"due"``/``"manual"`` carry per-question ``outcomes``."""

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
        control: WorkerControlPort | None = None,
        event_sink: WorkerEventSink | None = None,
    ) -> None:
        self._questions = questions
        self._runner = runner
        self._scheduler = scheduler
        self._last_run_at = last_run_at
        self._control = control
        self._event_sink = event_sink

    @property
    def last_run_at(self) -> datetime | None:
        return self._last_run_at

    @property
    def questions_count(self) -> int:
        """The size of the combined question set every cycle checks for gaps — a
        composition root's Learning Reports need this to report "questions considered",
        which ``CycleOutcome.outcomes`` alone cannot: it holds only the *actionable* gaps a
        cycle actually researched, not the full catalog every cycle checks against."""
        return len(self._questions)

    async def _effective_settings(self) -> WorkerControlSettings:
        if self._control is None:
            return WorkerControlSettings(
                enabled=True, interval=self._scheduler.interval, manual_trigger_requested=False
            )
        return await self._control.get_settings()

    async def _emit(self, event_type: WorkerEventType, message: str, *, now: datetime) -> None:
        if self._event_sink is None:
            return
        await self._event_sink.record(
            WorkerEvent(event_type=event_type, message=message, occurred_at=now)
        )

    async def tick(self, *, now: datetime) -> CycleOutcome:
        """Run exactly one scheduling decision: skip if the worker is disabled or not yet
        due, otherwise research every actionable gap in the combined question set and record
        ``now`` as the last run. When a ``WorkerControlPort`` is injected, its settings
        (enabled/interval/manual trigger) are re-read on every call, so an admin's change
        takes effect on the very next poll without a process restart."""
        settings = await self._effective_settings()
        if not settings.enabled:
            return CycleOutcome(ran=False, reason="disabled", started_at=now)

        is_due = settings.manual_trigger_requested or LearningCycleScheduler(
            interval=settings.interval
        ).is_due(last_run_at=self._last_run_at, now=now)
        if not is_due:
            return CycleOutcome(ran=False, reason="not_due", started_at=now)

        reason = "manual" if settings.manual_trigger_requested else "due"
        await self._emit(
            WorkerEventType.CYCLE_STARTED, f"Learning cycle started ({reason})", now=now
        )
        try:
            outcomes = await self._runner.run(self._questions, now=now)
        except Exception as exc:  # noqa: BLE001 - reported, then re-raised: see class docstring
            await self._emit(WorkerEventType.ERROR, f"Learning cycle failed: {exc}", now=now)
            raise

        self._last_run_at = now
        if settings.manual_trigger_requested and self._control is not None:
            await self._control.clear_manual_trigger()

        stored_count = sum(1 for outcome in outcomes if outcome.stored)
        await self._emit(
            WorkerEventType.CYCLE_COMPLETED,
            f"Learning cycle completed: {len(outcomes)} question(s) researched, "
            f"{stored_count} stored",
            now=now,
        )
        return CycleOutcome(ran=True, reason=reason, started_at=now, outcomes=tuple(outcomes))

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
