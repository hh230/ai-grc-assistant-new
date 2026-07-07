"""Unit tests for AutonomousRegulationIngestionWorker: tick() only ingests when the scheduler
says a cycle is due, respects the shared WorkerControlPort (disabled/manual trigger/dynamic
interval), and emits the shared WorkerEvent timeline around a cycle — mirroring
grc_knowledge_worker's own test_worker.py, since this worker reuses that exact seam. No real
network, database, or LLM call anywhere in this suite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from grc_knowledge_worker import LearningCycleScheduler, WorkerControlSettings, WorkerEvent
from grc_regulation_ingestion import AutonomousRegulationIngestionWorker, RegulationCatalogEntry

_ENTRY = RegulationCatalogEntry(
    name_ar="النظام الأساسي للحكم",
    category="الأنظمة الأساسية",
    source_url="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/x/1",
)


@dataclass(frozen=True)
class _FakeOutcome:
    source_url: str
    stored: bool
    error: str | None = None


class FakeCatalogSource:
    def __init__(self, catalog: tuple[RegulationCatalogEntry, ...]) -> None:
        self._catalog = catalog
        self.load_calls = 0

    async def load(self) -> tuple[RegulationCatalogEntry, ...]:
        self.load_calls += 1
        return self._catalog


class FakeRunner:
    def __init__(self, outcomes: tuple[_FakeOutcome, ...]) -> None:
        self._outcomes = outcomes
        self.calls: list[tuple[tuple[RegulationCatalogEntry, ...], datetime]] = []

    async def run(
        self, catalog: tuple[RegulationCatalogEntry, ...], *, now: datetime
    ) -> tuple[_FakeOutcome, ...]:
        self.calls.append((catalog, now))
        return self._outcomes


class FakeControl:
    def __init__(self, settings: WorkerControlSettings) -> None:
        self._settings = settings
        self.clear_calls = 0

    async def get_settings(self) -> WorkerControlSettings:
        return self._settings

    async def clear_manual_trigger(self) -> None:
        self.clear_calls += 1
        self._settings = WorkerControlSettings(
            enabled=self._settings.enabled,
            interval=self._settings.interval,
            manual_trigger_requested=False,
        )


class FakeEventSink:
    def __init__(self) -> None:
        self.events: list[WorkerEvent] = []

    async def record(self, event: WorkerEvent) -> None:
        self.events.append(event)


def _worker(
    catalog_source: FakeCatalogSource,
    runner: FakeRunner,
    *,
    interval: timedelta = timedelta(days=1),
    control: FakeControl | None = None,
    event_sink: FakeEventSink | None = None,
) -> AutonomousRegulationIngestionWorker:
    return AutonomousRegulationIngestionWorker(
        catalog_source=catalog_source,
        runner=runner,
        scheduler=LearningCycleScheduler(interval=interval),
        control=control,
        event_sink=event_sink,
    )


async def test_tick_runs_and_loads_catalog_when_never_run_before() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    catalog_source = FakeCatalogSource((_ENTRY,))
    runner = FakeRunner((_FakeOutcome(source_url=_ENTRY.source_url, stored=True),))
    worker = _worker(catalog_source, runner)

    outcome = await worker.tick(now=now)

    assert outcome.ran is True
    assert outcome.reason == "due"
    assert outcome.stored_count == 1
    assert catalog_source.load_calls == 1
    assert runner.calls == [((_ENTRY,), now)]
    assert worker.last_run_at == now


async def test_tick_skips_when_not_yet_due() -> None:
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    catalog_source = FakeCatalogSource((_ENTRY,))
    runner = FakeRunner((_FakeOutcome(source_url=_ENTRY.source_url, stored=True),))
    worker = _worker(catalog_source, runner, interval=timedelta(days=1))

    await worker.tick(now=first)
    outcome = await worker.tick(now=second)

    assert outcome.ran is False
    assert outcome.reason == "not_due"
    assert catalog_source.load_calls == 1  # not reloaded on the skipped tick
    assert len(runner.calls) == 1


async def test_tick_skips_when_control_reports_disabled() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    catalog_source = FakeCatalogSource((_ENTRY,))
    runner = FakeRunner((_FakeOutcome(source_url=_ENTRY.source_url, stored=True),))
    control = FakeControl(
        WorkerControlSettings(
            enabled=False, interval=timedelta(hours=1), manual_trigger_requested=False
        )
    )
    worker = _worker(catalog_source, runner, control=control)

    outcome = await worker.tick(now=now)

    assert outcome.ran is False
    assert outcome.reason == "disabled"
    assert catalog_source.load_calls == 0
    assert runner.calls == []


async def test_manual_trigger_runs_early_and_is_cleared_after() -> None:
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(minutes=1)
    catalog_source = FakeCatalogSource((_ENTRY,))
    runner = FakeRunner((_FakeOutcome(source_url=_ENTRY.source_url, stored=True),))
    control = FakeControl(
        WorkerControlSettings(
            enabled=True, interval=timedelta(days=1), manual_trigger_requested=False
        )
    )
    worker = _worker(catalog_source, runner, interval=timedelta(days=1), control=control)
    await worker.tick(now=first)  # establishes last_run_at via the normal "due" path

    control._settings = WorkerControlSettings(  # noqa: SLF001 - test-only fake mutation
        enabled=True, interval=timedelta(days=1), manual_trigger_requested=True
    )
    outcome = await worker.tick(now=second)

    assert outcome.ran is True
    assert outcome.reason == "manual"
    assert control.clear_calls == 1


async def test_tick_emits_cycle_started_loaded_and_completed_events() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    catalog_source = FakeCatalogSource((_ENTRY,))
    runner = FakeRunner((_FakeOutcome(source_url=_ENTRY.source_url, stored=True),))
    sink = FakeEventSink()
    worker = _worker(catalog_source, runner, event_sink=sink)

    await worker.tick(now=now)

    assert [event.event_type.value for event in sink.events] == [
        "cycle_started",
        "questions_loaded",
        "cycle_completed",
    ]


async def test_tick_emits_an_error_event_and_reraises_when_the_runner_fails() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    class FailingRunner:
        async def run(
            self, catalog: tuple[RegulationCatalogEntry, ...], *, now: datetime
        ) -> tuple[_FakeOutcome, ...]:
            raise RuntimeError("boom")

    sink = FakeEventSink()
    worker = AutonomousRegulationIngestionWorker(
        catalog_source=FakeCatalogSource((_ENTRY,)),
        runner=FailingRunner(),
        scheduler=LearningCycleScheduler(interval=timedelta(days=1)),
        event_sink=sink,
    )

    with pytest.raises(RuntimeError, match="boom"):
        await worker.tick(now=now)

    assert [event.event_type.value for event in sink.events] == [
        "cycle_started",
        "questions_loaded",
        "error",
    ]
    assert worker.last_run_at is None
