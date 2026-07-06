"""Unit tests for AutonomousKnowledgeWorker: tick() only researches when the scheduler says a
cycle is due, advances last_run_at exactly once per run, and run_loop() repeats tick() a
bounded number of times using an injected clock and sleep — no real time, network, database,
or LLM call anywhere in this suite. KI-P5 (ADR-0029) adds fakes for the optional
WorkerControlPort/WorkerEventSink seams: disabled/manual-trigger/dynamic-interval behavior,
and the cycle_started/cycle_completed/error events emitted around a cycle."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from grc_knowledge_intelligence import KnowledgeDomain, KnowledgeQuestion
from grc_knowledge_worker import (
    AutonomousKnowledgeWorker,
    GapResearchOutcomeLike,
    LearningCycleScheduler,
    WorkerControlSettings,
    WorkerEvent,
)

_QUESTION = KnowledgeQuestion(
    question_id="governance.q1",
    question="What governance practices apply?",
    domain=KnowledgeDomain.GOVERNANCE,
    category="governance",
)


@dataclass(frozen=True)
class _FakeOutcome:
    question_id: str
    stored: bool
    error: str | None = None


class FakeRunner:
    def __init__(self, outcomes: tuple[_FakeOutcome, ...]) -> None:
        self._outcomes = outcomes
        self.calls: list[tuple[tuple[KnowledgeQuestion, ...], datetime]] = []

    async def run(
        self, questions: tuple[KnowledgeQuestion, ...], *, now: datetime
    ) -> tuple[_FakeOutcome, ...]:
        self.calls.append((questions, now))
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
    runner: FakeRunner,
    *,
    interval: timedelta = timedelta(days=1),
    control: FakeControl | None = None,
    event_sink: FakeEventSink | None = None,
) -> AutonomousKnowledgeWorker:
    return AutonomousKnowledgeWorker(
        questions=(_QUESTION,),
        runner=runner,
        scheduler=LearningCycleScheduler(interval=interval),
        control=control,
        event_sink=event_sink,
    )


async def test_tick_runs_and_stores_when_never_run_before() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    worker = _worker(runner)

    outcome = await worker.tick(now=now)

    assert outcome.ran is True
    assert outcome.reason == "due"
    assert outcome.stored_count == 1
    assert worker.last_run_at == now
    assert runner.calls == [((_QUESTION,), now)]


async def test_tick_skips_when_not_yet_due() -> None:
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    worker = _worker(runner, interval=timedelta(days=1))

    await worker.tick(now=first)
    outcome = await worker.tick(now=second)

    assert outcome.ran is False
    assert outcome.reason == "not_due"
    assert outcome.outcomes == ()
    assert worker.last_run_at == first  # unchanged by the skipped tick
    assert len(runner.calls) == 1


async def test_tick_runs_again_once_the_interval_elapses() -> None:
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(days=1)
    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    worker = _worker(runner, interval=timedelta(days=1))

    await worker.tick(now=first)
    outcome = await worker.tick(now=second)

    assert outcome.ran is True
    assert worker.last_run_at == second
    assert len(runner.calls) == 2


async def test_run_loop_ticks_max_iterations_times_and_sleeps_between() -> None:
    clock_values = iter(
        [
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 2, tzinfo=timezone.utc),
            datetime(2026, 1, 3, tzinfo=timezone.utc),
        ]
    )
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    worker = _worker(runner, interval=timedelta(days=1))

    results = await worker.run_loop(
        clock=lambda: next(clock_values),
        sleep=fake_sleep,
        poll_interval_seconds=42.0,
        max_iterations=3,
    )

    assert len(results) == 3
    assert all(result.ran for result in results)
    # Sleeps only *between* iterations, never after the last one.
    assert sleep_calls == [42.0, 42.0]


async def test_run_loop_rejects_a_non_positive_max_iterations() -> None:
    runner = FakeRunner(())
    worker = _worker(runner)

    async def fake_sleep(seconds: float) -> None:
        pass

    with pytest.raises(ValueError, match="max_iterations"):
        await worker.run_loop(
            clock=lambda: datetime.now(timezone.utc),
            sleep=fake_sleep,
            poll_interval_seconds=1.0,
            max_iterations=0,
        )


async def test_tick_skips_when_control_reports_disabled() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    control = FakeControl(
        WorkerControlSettings(
            enabled=False, interval=timedelta(hours=1), manual_trigger_requested=False
        )
    )
    worker = _worker(runner, control=control)

    outcome = await worker.tick(now=now)

    assert outcome.ran is False
    assert outcome.reason == "disabled"
    assert runner.calls == []
    assert worker.last_run_at is None


async def test_tick_honors_a_control_interval_shorter_than_the_static_scheduler() -> None:
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    control = FakeControl(
        WorkerControlSettings(
            enabled=True, interval=timedelta(minutes=30), manual_trigger_requested=False
        )
    )
    # The static scheduler says "due once a day", but the injected control settings' shorter
    # interval is what actually governs cadence.
    worker = _worker(runner, interval=timedelta(days=1), control=control)

    await worker.tick(now=first)
    outcome = await worker.tick(now=second)

    assert outcome.ran is True
    assert outcome.reason == "due"


async def test_manual_trigger_runs_early_and_is_cleared_after() -> None:
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(minutes=1)
    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    # Not due for another day, but a pending manual trigger overrides that.
    control = FakeControl(
        WorkerControlSettings(
            enabled=True, interval=timedelta(days=1), manual_trigger_requested=False
        )
    )
    worker = _worker(runner, interval=timedelta(days=1), control=control)
    await worker.tick(now=first)  # establishes last_run_at via the normal "due" path

    control._settings = WorkerControlSettings(  # noqa: SLF001 - test-only fake mutation
        enabled=True, interval=timedelta(days=1), manual_trigger_requested=True
    )
    outcome = await worker.tick(now=second)

    assert outcome.ran is True
    assert outcome.reason == "manual"
    assert control.clear_calls == 1


async def test_tick_emits_cycle_started_and_completed_events() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    sink = FakeEventSink()
    worker = _worker(runner, event_sink=sink)

    await worker.tick(now=now)

    assert [event.event_type.value for event in sink.events] == ["cycle_started", "cycle_completed"]
    assert all(event.occurred_at == now for event in sink.events)


async def test_tick_emits_no_events_when_not_due() -> None:
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(hours=1)
    runner = FakeRunner((_FakeOutcome(question_id=_QUESTION.question_id, stored=True),))
    sink = FakeEventSink()
    worker = _worker(runner, interval=timedelta(days=1), event_sink=sink)

    await worker.tick(now=first)
    sink.events.clear()
    await worker.tick(now=second)

    assert sink.events == []


async def test_tick_emits_an_error_event_and_reraises_when_the_runner_fails() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    class FailingRunner:
        async def run(
            self, questions: tuple[KnowledgeQuestion, ...], *, now: datetime
        ) -> Sequence[GapResearchOutcomeLike]:
            raise RuntimeError("boom")

    sink = FakeEventSink()
    worker = AutonomousKnowledgeWorker(
        questions=(_QUESTION,),
        runner=FailingRunner(),
        scheduler=LearningCycleScheduler(interval=timedelta(days=1)),
        event_sink=sink,
    )

    with pytest.raises(RuntimeError, match="boom"):
        await worker.tick(now=now)

    assert [event.event_type.value for event in sink.events] == ["cycle_started", "error"]
    assert worker.last_run_at is None
