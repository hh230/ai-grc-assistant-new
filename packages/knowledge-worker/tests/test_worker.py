"""Unit tests for AutonomousKnowledgeWorker: tick() only researches when the scheduler says a
cycle is due, advances last_run_at exactly once per run, and run_loop() repeats tick() a
bounded number of times using an injected clock and sleep — no real time, network, database,
or LLM call anywhere in this suite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from grc_knowledge_intelligence import KnowledgeDomain, KnowledgeQuestion
from grc_knowledge_worker import AutonomousKnowledgeWorker, LearningCycleScheduler

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


class FakeRunner:
    def __init__(self, outcomes: tuple[_FakeOutcome, ...]) -> None:
        self._outcomes = outcomes
        self.calls: list[tuple[tuple[KnowledgeQuestion, ...], datetime]] = []

    async def run(
        self, questions: tuple[KnowledgeQuestion, ...], *, now: datetime
    ) -> tuple[_FakeOutcome, ...]:
        self.calls.append((questions, now))
        return self._outcomes


def _worker(
    runner: FakeRunner, *, interval: timedelta = timedelta(days=1)
) -> AutonomousKnowledgeWorker:
    return AutonomousKnowledgeWorker(
        questions=(_QUESTION,),
        runner=runner,
        scheduler=LearningCycleScheduler(interval=interval),
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
