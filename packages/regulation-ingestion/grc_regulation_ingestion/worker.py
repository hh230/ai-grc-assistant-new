"""``AutonomousRegulationIngestionWorker`` — the Saudi Regulations Ingestion Pipeline's pure
orchestrator (Knowledge Intelligence KI-P6, ADR-0030).

Per explicit instruction, this reuses KI-P4/KI-P5's worker architecture rather than building a
parallel one: ``grc_knowledge_worker.LearningCycleScheduler`` for cadence,
``WorkerControlPort``/``WorkerControlSettings`` for the same admin enable/disable/interval/
manual-trigger seam, and ``WorkerEventSink``/``WorkerEvent``/``WorkerEventType`` for the same
activity-timeline vocabulary the AI Worker Control Center already renders — no second event
vocabulary, no second admin control concept. ``tick()``'s shape (settings → due-check → cycle →
clear manual trigger → events) is deliberately the same shape as
``grc_knowledge_worker.AutonomousKnowledgeWorker.tick`` for the same reason.

One structural difference from KI-P4, and why: KI-P4's question catalog is fixed local JSON,
loaded once at process start. This pipeline's catalog is itself a live remote resource (the
Google Drive index PDF can gain new regulations over time), so it is re-loaded once per cycle
via an injected ``CatalogSourcePort`` rather than held as a fixed tuple — everything else about
the cadence/control/event handling is unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from grc_knowledge_worker import (
    LearningCycleScheduler,
    WorkerControlPort,
    WorkerControlSettings,
    WorkerEvent,
    WorkerEventSink,
    WorkerEventType,
)

from .models import RegulationCatalogEntry


class CatalogSourcePort(Protocol):
    """Loads the current regulation catalog (fetches + parses the index document)."""

    async def load(self) -> tuple[RegulationCatalogEntry, ...]: ...


class RegulationOutcomeLike(Protocol):
    """The shape of one catalog entry's result the worker reports on — satisfied structurally
    by ``grc_regulation_ingestion_adapters.RegulationIngestionOutcome`` without this package
    importing it (the same anti-coupling idiom ``grc_knowledge_worker.GapResearchOutcomeLike``
    already established)."""

    @property
    def source_url(self) -> str: ...

    @property
    def stored(self) -> bool: ...

    @property
    def error(self) -> str | None: ...


class RegulationFetchRunnerPort(Protocol):
    """Matches ``grc_regulation_ingestion_adapters.RegulationGapRunner.run`` exactly, so the
    real runner can be injected directly with no adapter glue."""

    async def run(
        self, catalog: tuple[RegulationCatalogEntry, ...], *, now: datetime
    ) -> Sequence[RegulationOutcomeLike]: ...


@dataclass(frozen=True)
class CycleOutcome:
    """What happened on one ``tick``. ``reason`` is one of: ``"disabled"`` (an admin paused
    the pipeline), ``"not_due"`` (the scheduler says wait), ``"due"`` (a normal scheduled
    cycle ran), or ``"manual"`` (an admin's manual trigger ran the cycle early)."""

    ran: bool
    reason: str
    started_at: datetime
    outcomes: tuple[RegulationOutcomeLike, ...] = ()

    @property
    def stored_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.stored)


class AutonomousRegulationIngestionWorker:
    """Ties the scheduler, the injected catalog source, and the fetch/parse/store runner
    together into a repeatable ingestion cycle. One catalog entry's failure never blocks
    another's (enforced by the injected runner, the same fail-safe posture
    ``KnowledgeGapResearchRunner`` already holds itself to)."""

    def __init__(
        self,
        *,
        catalog_source: CatalogSourcePort,
        runner: RegulationFetchRunnerPort,
        scheduler: LearningCycleScheduler,
        last_run_at: datetime | None = None,
        control: WorkerControlPort | None = None,
        event_sink: WorkerEventSink | None = None,
    ) -> None:
        self._catalog_source = catalog_source
        self._runner = runner
        self._scheduler = scheduler
        self._last_run_at = last_run_at
        self._control = control
        self._event_sink = event_sink

    @property
    def last_run_at(self) -> datetime | None:
        return self._last_run_at

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
        """Run exactly one scheduling decision: skip if disabled or not yet due, otherwise
        load the current catalog and ingest every entry via the injected runner."""
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
            WorkerEventType.CYCLE_STARTED,
            f"Regulation ingestion cycle started ({reason})",
            now=now,
        )
        try:
            catalog = await self._catalog_source.load()
            await self._emit(
                WorkerEventType.QUESTIONS_LOADED,
                f"Loaded {len(catalog)} regulation(s) from the index catalog",
                now=now,
            )
            outcomes = await self._runner.run(catalog, now=now)
        except Exception as exc:  # noqa: BLE001 - reported, then re-raised: see class docstring
            await self._emit(
                WorkerEventType.ERROR, f"Regulation ingestion cycle failed: {exc}", now=now
            )
            raise

        self._last_run_at = now
        if settings.manual_trigger_requested and self._control is not None:
            await self._control.clear_manual_trigger()

        stored_count = sum(1 for outcome in outcomes if outcome.stored)
        await self._emit(
            WorkerEventType.CYCLE_COMPLETED,
            f"Regulation ingestion cycle completed: {len(outcomes)} regulation(s) processed, "
            f"{stored_count} stored",
            now=now,
        )
        return CycleOutcome(ran=True, reason=reason, started_at=now, outcomes=tuple(outcomes))
