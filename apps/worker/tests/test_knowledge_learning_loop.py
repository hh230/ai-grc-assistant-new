"""Deterministic tests for the Knowledge Worker composition root: real data loading (no
network), environment-driven configuration (fail-fast on missing/invalid config), and the
real infinite-loop's stop/skip/tick semantics against a fake runner. Deliberately excludes any
test that would open a real database connection, make a real HTTP request, or call a real LLM
— those remain a manual/opt-in concern for a deployed environment, the same boundary every
sibling Knowledge Intelligence package already holds itself to (see ADR-0028)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
from grc_knowledge_intelligence import KnowledgeDomain, KnowledgeQuestion
from grc_knowledge_worker import AutonomousKnowledgeWorker, LearningCycleScheduler
from grc_worker.knowledge_learning_loop import (
    WorkerConfigurationError,
    WorkerSettings,
    _repo_root,
    load_questions,
    load_trusted_sources,
    run_forever,
)

_QUESTION = KnowledgeQuestion(
    question_id="governance.q1",
    question="What governance practices apply?",
    domain=KnowledgeDomain.GOVERNANCE,
    category="governance",
)


def test_load_questions_combines_the_real_catalog_and_ontology_without_collision() -> None:
    questions = load_questions(_repo_root())

    ids = [question.question_id for question in questions]
    assert len(ids) == len(set(ids))
    assert len(questions) > 0


def test_load_trusted_sources_loads_the_real_curated_catalog() -> None:
    catalog = load_trusted_sources(_repo_root())

    assert len(catalog) > 0
    assert all(entry.source.source_id for entry in catalog)


def test_worker_settings_requires_database_url() -> None:
    with pytest.raises(WorkerConfigurationError, match="DATABASE_URL"):
        WorkerSettings.from_env({})


def test_worker_settings_rejects_a_data_root_missing_expected_directories(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(WorkerConfigurationError, match="does not look like the repo root"):
        WorkerSettings.from_env(
            {"DATABASE_URL": "postgresql://u:p@localhost/db", "GRC_DATA_ROOT": str(tmp_path)}
        )


def test_worker_settings_from_env_uses_defaults() -> None:
    settings = WorkerSettings.from_env({"DATABASE_URL": "postgresql://u:p@localhost/db"})

    assert settings.database_url == "postgresql://u:p@localhost/db"
    assert settings.data_root == _repo_root()
    assert settings.cycle_interval == timedelta(hours=24)
    assert settings.poll_interval_seconds == 3600.0
    assert settings.max_sources == 3
    assert settings.max_documents_per_source == 8


def test_worker_settings_from_env_reads_overrides() -> None:
    settings = WorkerSettings.from_env(
        {
            "DATABASE_URL": "postgresql://u:p@localhost/db",
            "GRC_KNOWLEDGE_WORKER_CYCLE_INTERVAL_HOURS": "12",
            "GRC_KNOWLEDGE_WORKER_POLL_INTERVAL_SECONDS": "60",
            "GRC_KNOWLEDGE_WORKER_MAX_SOURCES": "5",
            "GRC_KNOWLEDGE_WORKER_MAX_DOCUMENTS_PER_SOURCE": "15",
        }
    )

    assert settings.cycle_interval == timedelta(hours=12)
    assert settings.poll_interval_seconds == 60.0
    assert settings.max_sources == 5
    assert settings.max_documents_per_source == 15


@dataclass(frozen=True)
class _FakeOutcome:
    question_id: str
    stored: bool
    error: str | None = None


class FakeRunner:
    def __init__(self) -> None:
        self.call_count = 0

    async def run(
        self, questions: tuple[KnowledgeQuestion, ...], *, now: datetime
    ) -> tuple[_FakeOutcome, ...]:
        self.call_count += 1
        return (_FakeOutcome(question_id=_QUESTION.question_id, stored=True),)


def _worker(runner: FakeRunner) -> AutonomousKnowledgeWorker:
    return AutonomousKnowledgeWorker(
        questions=(_QUESTION,),
        runner=runner,
        scheduler=LearningCycleScheduler(interval=timedelta(seconds=0.01)),
    )


async def test_run_forever_exits_immediately_if_already_stopped() -> None:
    runner = FakeRunner()
    worker = _worker(runner)
    stop_event = asyncio.Event()
    stop_event.set()

    await run_forever(worker, poll_interval_seconds=60.0, stop_event=stop_event)

    assert runner.call_count == 0


async def test_run_forever_ticks_then_stops_when_signalled_during_the_poll_wait() -> None:
    runner = FakeRunner()
    worker = _worker(runner)
    stop_event = asyncio.Event()

    async def _stop_after_first_tick() -> None:
        await asyncio.sleep(0)
        stop_event.set()

    task = asyncio.create_task(_stop_after_first_tick())
    await run_forever(worker, poll_interval_seconds=0.01, stop_event=stop_event)
    await task

    assert runner.call_count >= 1


class FakeRunHistory:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def record_run(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


async def test_run_forever_records_run_history_when_a_cycle_ran() -> None:
    runner = FakeRunner()
    worker = _worker(runner)
    stop_event = asyncio.Event()
    run_history = FakeRunHistory()

    async def _stop_after_first_tick() -> None:
        await asyncio.sleep(0)
        stop_event.set()

    task = asyncio.create_task(_stop_after_first_tick())
    await run_forever(
        worker, poll_interval_seconds=0.01, stop_event=stop_event, run_history=run_history
    )
    await task

    assert len(run_history.calls) >= 1
    call = run_history.calls[0]
    assert call["reason"] == "due"
    assert call["questions_considered"] == worker.questions_count
    assert call["gaps_detected"] == 1
    assert call["items_saved"] == 1
    assert call["error_count"] == 0


async def test_run_forever_survives_a_tick_that_raises() -> None:
    class RaisingRunner:
        async def run(
            self, questions: tuple[KnowledgeQuestion, ...], *, now: datetime
        ) -> tuple[_FakeOutcome, ...]:
            raise RuntimeError("boom")

    worker = AutonomousKnowledgeWorker(
        questions=(_QUESTION,),
        runner=RaisingRunner(),
        scheduler=LearningCycleScheduler(interval=timedelta(seconds=0.01)),
    )
    stop_event = asyncio.Event()

    async def _stop_soon() -> None:
        await asyncio.sleep(0)
        stop_event.set()

    task = asyncio.create_task(_stop_soon())
    # Must not raise, despite the runner raising on every tick.
    await run_forever(worker, poll_interval_seconds=0.01, stop_event=stop_event)
    await task
