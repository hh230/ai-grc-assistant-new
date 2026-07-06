"""Integration tests for WorkerControlRepository/WorkerRunHistoryRepository/
WorkerEventRepository against apps/web's live `worker_control`/`worker_run_history`/
`worker_events` tables (Knowledge Intelligence KI-P5, ADR-0029)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from grc_knowledge_worker import WorkerEvent, WorkerEventType
from grc_persistence_web import (
    Database,
    WorkerControlRepository,
    WorkerEventRepository,
    WorkerRunHistoryRepository,
)


async def _reset_control(database: Database) -> None:
    async with database.pool.acquire() as connection:
        await connection.execute(
            "UPDATE worker_control SET enabled = true, interval_hours = 12, "
            "manual_trigger_requested_at = NULL, updated_by = NULL WHERE id = 'default'"
        )


async def test_get_settings_reflects_the_singleton_row(database: Database) -> None:
    await _reset_control(database)
    repository = WorkerControlRepository(database)

    settings = await repository.get_settings()

    assert settings.enabled is True
    assert settings.interval == timedelta(hours=12)
    assert settings.manual_trigger_requested is False


async def test_set_enabled_and_set_interval_hours_round_trip(database: Database) -> None:
    await _reset_control(database)
    repository = WorkerControlRepository(database)
    try:
        disabled = await repository.set_enabled(False, updated_by="admin-1")
        assert disabled.enabled is False
        assert disabled.updated_by == "admin-1"

        reconfigured = await repository.set_interval_hours(6.0, updated_by="admin-2")
        assert reconfigured.interval_hours == 6.0

        settings = await repository.get_settings()
        assert settings.enabled is False
        assert settings.interval == timedelta(hours=6)
    finally:
        await _reset_control(database)


async def test_manual_trigger_request_and_clear_round_trip(database: Database) -> None:
    await _reset_control(database)
    repository = WorkerControlRepository(database)
    try:
        requested = await repository.request_manual_trigger(updated_by="admin-1")
        assert requested.manual_trigger_requested_at is not None

        settings = await repository.get_settings()
        assert settings.manual_trigger_requested is True

        await repository.clear_manual_trigger()
        settings_after = await repository.get_settings()
        assert settings_after.manual_trigger_requested is False
    finally:
        await _reset_control(database)


async def _delete_run(database: Database, run_id: str) -> None:
    async with database.pool.acquire() as connection:
        await connection.execute("DELETE FROM worker_run_history WHERE id = $1", run_id)


async def test_run_history_records_and_lists_most_recent_first(database: Database) -> None:
    repository = WorkerRunHistoryRepository(database)
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)

    first = await repository.record_run(
        reason="due",
        started_at=started,
        completed_at=started + timedelta(minutes=1),
        questions_considered=5,
        gaps_detected=2,
        items_saved=1,
        error_count=0,
    )
    second = await repository.record_run(
        reason="manual",
        started_at=started + timedelta(hours=1),
        completed_at=started + timedelta(hours=1, minutes=1),
        questions_considered=5,
        gaps_detected=1,
        items_saved=1,
        error_count=0,
    )
    try:
        latest = await repository.get_latest()
        assert latest is not None
        assert latest.id == second.id
        assert latest.reason == "manual"

        recent = await repository.list_recent(limit=50)
        ids_in_order = [run.id for run in recent]
        assert ids_in_order.index(second.id) < ids_in_order.index(first.id)
    finally:
        await _delete_run(database, first.id)
        await _delete_run(database, second.id)


async def _delete_events_by_question_id(database: Database, question_id: str) -> None:
    async with database.pool.acquire() as connection:
        await connection.execute("DELETE FROM worker_events WHERE question_id = $1", question_id)


async def _delete_events_by_actor(database: Database, actor_user_id: str) -> None:
    async with database.pool.acquire() as connection:
        await connection.execute(
            "DELETE FROM worker_events WHERE actor_user_id = $1", actor_user_id
        )


async def test_event_repository_records_worker_events_and_admin_actions(
    database: Database,
) -> None:
    repository = WorkerEventRepository(database)
    occurred_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    question_id = f"test.{uuid.uuid4()}"
    actor_user_id = f"test-admin-{uuid.uuid4()}"
    try:
        await repository.record(
            WorkerEvent(
                event_type=WorkerEventType.ITEM_SAVED,
                message="Saved a test item",
                occurred_at=occurred_at,
                question_id=question_id,
                metadata={"domain": "governance"},
            )
        )
        await repository.record_admin_action(
            event_type="interval_changed",
            message="Interval changed to 6 hours",
            actor_user_id=actor_user_id,
            actor_tenant_id="tenant-1",
            metadata={"interval_hours": "6"},
        )

        recent = await repository.list_recent(limit=50)
        saved_event = next(event for event in recent if event.question_id == question_id)
        assert saved_event.event_type == "item_saved"
        assert saved_event.metadata == {"domain": "governance"}
        assert saved_event.actor_user_id is None

        admin_event = next(event for event in recent if event.actor_user_id == actor_user_id)
        assert admin_event.event_type == "interval_changed"
        assert admin_event.actor_tenant_id == "tenant-1"
    finally:
        await _delete_events_by_question_id(database, question_id)
        await _delete_events_by_actor(database, actor_user_id)
