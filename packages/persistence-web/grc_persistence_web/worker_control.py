"""Read/write access to apps/web's `worker_control`/`worker_run_history`/`worker_events`
tables — the durable state behind the Admin AI Worker Control Center (Knowledge Intelligence
KI-P5, ADR-0029): the enable/disable + interval + manual-trigger settings
``AutonomousKnowledgeWorker.tick`` re-reads on every poll, the per-cycle run history "last
run"/"next run" and learning reports are computed from, and the append-only activity timeline
(and, for admin-control event types, the audit trail — CLAUDE.md §19/§23).

Platform-scope, like `knowledge_items` (KI-P1, ADR-0025): exactly one knowledge worker process
exists, so `worker_control` is a singleton row, not a table keyed by tenant.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from grc_knowledge_worker import WorkerControlSettings, WorkerEvent

from .pool import Database

_CONTROL_COLUMNS = """
  id, enabled, interval_hours, manual_trigger_requested_at, updated_at, updated_by
"""
_RUN_COLUMNS = """
  id, reason, started_at, completed_at, questions_considered, gaps_detected, items_saved,
  error_count, created_at
"""
_EVENT_COLUMNS = """
  id, event_type, question_id, message, metadata, actor_user_id, actor_tenant_id, occurred_at
"""


@dataclass(frozen=True)
class WorkerControlRecord:
    id: str
    enabled: bool
    interval_hours: float
    manual_trigger_requested_at: datetime | None
    updated_at: datetime
    updated_by: str | None

    def to_settings(self) -> WorkerControlSettings:
        return WorkerControlSettings(
            enabled=self.enabled,
            interval=timedelta(hours=self.interval_hours),
            manual_trigger_requested=self.manual_trigger_requested_at is not None,
        )


@dataclass(frozen=True)
class WorkerRunRecord:
    id: str
    reason: str
    started_at: datetime
    completed_at: datetime | None
    questions_considered: int
    gaps_detected: int
    items_saved: int
    error_count: int
    created_at: datetime


@dataclass(frozen=True)
class WorkerEventRecord:
    id: str
    event_type: str
    question_id: str | None
    message: str
    metadata: dict[str, str]
    actor_user_id: str | None
    actor_tenant_id: str | None
    occurred_at: datetime


def _to_control_record(row: object) -> WorkerControlRecord:
    return WorkerControlRecord(
        id=row["id"],  # type: ignore[index]
        enabled=row["enabled"],  # type: ignore[index]
        interval_hours=row["interval_hours"],  # type: ignore[index]
        manual_trigger_requested_at=row["manual_trigger_requested_at"],  # type: ignore[index]
        updated_at=row["updated_at"],  # type: ignore[index]
        updated_by=row["updated_by"],  # type: ignore[index]
    )


def _to_run_record(row: object) -> WorkerRunRecord:
    return WorkerRunRecord(
        id=row["id"],  # type: ignore[index]
        reason=row["reason"],  # type: ignore[index]
        started_at=row["started_at"],  # type: ignore[index]
        completed_at=row["completed_at"],  # type: ignore[index]
        questions_considered=row["questions_considered"],  # type: ignore[index]
        gaps_detected=row["gaps_detected"],  # type: ignore[index]
        items_saved=row["items_saved"],  # type: ignore[index]
        error_count=row["error_count"],  # type: ignore[index]
        created_at=row["created_at"],  # type: ignore[index]
    )


def _to_event_record(row: object) -> WorkerEventRecord:
    return WorkerEventRecord(
        id=row["id"],  # type: ignore[index]
        event_type=row["event_type"],  # type: ignore[index]
        question_id=row["question_id"],  # type: ignore[index]
        message=row["message"],  # type: ignore[index]
        metadata=json.loads(row["metadata"]),  # type: ignore[index]
        actor_user_id=row["actor_user_id"],  # type: ignore[index]
        actor_tenant_id=row["actor_tenant_id"],  # type: ignore[index]
        occurred_at=row["occurred_at"],  # type: ignore[index]
    )


class WorkerControlRepository:
    """Implements ``grc_knowledge_worker.WorkerControlPort`` against the `worker_control`
    singleton row, plus the admin-facing writes (enable/disable, interval, manual trigger) the
    Control Center's API needs."""

    _ID = "default"

    def __init__(self, database: Database) -> None:
        self._database = database

    async def _get_row(self) -> WorkerControlRecord:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_CONTROL_COLUMNS} FROM worker_control WHERE id = $1", self._ID
            )
        assert row is not None  # noqa: S101 - the migration seeds this singleton row
        return _to_control_record(row)

    async def get_settings(self) -> WorkerControlSettings:
        return (await self._get_row()).to_settings()

    async def get(self) -> WorkerControlRecord:
        return await self._get_row()

    async def clear_manual_trigger(self) -> None:
        async with self._database.pool.acquire() as connection:
            await connection.execute(
                "UPDATE worker_control SET manual_trigger_requested_at = NULL, "
                "updated_at = now() WHERE id = $1",
                self._ID,
            )

    async def set_enabled(self, enabled: bool, *, updated_by: str) -> WorkerControlRecord:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                UPDATE worker_control SET enabled = $2, updated_at = now(), updated_by = $3
                WHERE id = $1
                RETURNING {_CONTROL_COLUMNS}
                """,
                self._ID,
                enabled,
                updated_by,
            )
        assert row is not None  # noqa: S101 - the migration seeds this singleton row
        return _to_control_record(row)

    async def set_interval_hours(
        self, interval_hours: float, *, updated_by: str
    ) -> WorkerControlRecord:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                UPDATE worker_control SET interval_hours = $2, updated_at = now(), updated_by = $3
                WHERE id = $1
                RETURNING {_CONTROL_COLUMNS}
                """,
                self._ID,
                interval_hours,
                updated_by,
            )
        assert row is not None  # noqa: S101 - the migration seeds this singleton row
        return _to_control_record(row)

    async def request_manual_trigger(self, *, updated_by: str) -> WorkerControlRecord:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                UPDATE worker_control
                SET manual_trigger_requested_at = now(), updated_at = now(), updated_by = $2
                WHERE id = $1
                RETURNING {_CONTROL_COLUMNS}
                """,
                self._ID,
                updated_by,
            )
        assert row is not None  # noqa: S101 - the migration seeds this singleton row
        return _to_control_record(row)


class WorkerRunHistoryRepository:
    """The per-cycle run history behind "last run"/"next run" and the Learning Reports trend
    — one row per cycle that actually ran, written once after ``tick()`` returns."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def record_run(
        self,
        *,
        reason: str,
        started_at: datetime,
        completed_at: datetime,
        questions_considered: int,
        gaps_detected: int,
        items_saved: int,
        error_count: int,
    ) -> WorkerRunRecord:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                INSERT INTO worker_run_history (
                  id, reason, started_at, completed_at, questions_considered, gaps_detected,
                  items_saved, error_count
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING {_RUN_COLUMNS}
                """,
                str(uuid.uuid4()),
                reason,
                started_at,
                completed_at,
                questions_considered,
                gaps_detected,
                items_saved,
                error_count,
            )
        assert row is not None  # noqa: S101 - RETURNING always yields the inserted row
        return _to_run_record(row)

    async def get_latest(self) -> WorkerRunRecord | None:
        async with self._database.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"SELECT {_RUN_COLUMNS} FROM worker_run_history ORDER BY started_at DESC LIMIT 1"
            )
        return _to_run_record(row) if row is not None else None

    async def list_recent(self, limit: int = 20) -> list[WorkerRunRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                f"SELECT {_RUN_COLUMNS} FROM worker_run_history ORDER BY started_at DESC LIMIT $1",
                limit,
            )
        return [_to_run_record(row) for row in rows]


class WorkerEventRepository:
    """Implements ``grc_knowledge_worker.WorkerEventSink`` for the worker's own cycle events,
    plus ``record_admin_action`` for the Control Center's admin-initiated actions (enable/
    disable, interval change, manual trigger request) — both write to the same append-only
    `worker_events` table the activity timeline reads."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def record(self, event: WorkerEvent) -> None:
        async with self._database.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO worker_events (
                  id, event_type, question_id, message, metadata, actor_user_id,
                  actor_tenant_id, occurred_at
                ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
                """,
                str(uuid.uuid4()),
                event.event_type.value,
                event.question_id,
                event.message,
                json.dumps(dict(event.metadata)),
                None,
                None,
                event.occurred_at,
            )

    async def record_admin_action(
        self,
        *,
        event_type: str,
        message: str,
        actor_user_id: str,
        actor_tenant_id: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        async with self._database.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO worker_events (
                  id, event_type, message, metadata, actor_user_id, actor_tenant_id
                ) VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                """,
                str(uuid.uuid4()),
                event_type,
                message,
                json.dumps(metadata or {}),
                actor_user_id,
                actor_tenant_id,
            )

    async def list_recent(self, limit: int = 50) -> list[WorkerEventRecord]:
        async with self._database.pool.acquire() as connection:
            rows = await connection.fetch(
                f"SELECT {_EVENT_COLUMNS} FROM worker_events ORDER BY occurred_at DESC LIMIT $1",
                limit,
            )
        return [_to_event_record(row) for row in rows]
