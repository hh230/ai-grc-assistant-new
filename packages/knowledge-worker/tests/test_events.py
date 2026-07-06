"""WorkerEvent is a plain, frozen value object — nothing to unit test beyond construction and
default metadata; the interesting behavior (tick() emitting events through an injected
WorkerEventSink) is covered in test_worker.py."""

from __future__ import annotations

from datetime import datetime, timezone

from grc_knowledge_worker import WorkerEvent, WorkerEventType


def test_worker_event_defaults_to_empty_metadata_and_no_question_id() -> None:
    event = WorkerEvent(
        event_type=WorkerEventType.CYCLE_STARTED,
        message="Learning cycle started (due)",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert event.question_id is None
    assert event.metadata == {}


def test_worker_event_carries_a_question_id_and_metadata_when_given() -> None:
    event = WorkerEvent(
        event_type=WorkerEventType.ITEM_SAVED,
        message="Saved an answer",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        question_id="governance.q1",
        metadata={"domain": "governance"},
    )
    assert event.question_id == "governance.q1"
    assert event.metadata == {"domain": "governance"}
