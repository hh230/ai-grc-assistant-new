"""Pure, driver-free translation between a `DomainEvent` and a plain outbox row (ADR 0043-S4 §8).
Imports no database driver and does no I/O, so the whole round-trip is unit-testable without
Postgres. `OutboxSink` / `OutboxRelay` (outbox.py) are the only modules that know psycopg; they
delegate all shape translation here.

Write side (`event_to_row`) reuses each event's canonical `to_dict()` — the platform's one
serialization convention — for the JSONB `payload`, and denormalizes the fields the relay needs to
index and dispatch without opening the blob (`event_name`, `trace_id`, `tenant_id`, `mission_id`,
`occurred_at`).

Read side rebuilds a **typed** `DomainEvent` via a name→class **registry** (`event_from_record`). An
`event_name` with no registered type raises `UnsupportedEventType` — there is deliberately **no
generic fallback event** (ADR 0043-S4 Rev.3 §8, Invariant I8). Every row carries a
`payload_schema_version`; an unknown version fails loud rather than guessing (as Slice 1's codec).
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from event_bus.events import (
    AnswerValidated,
    DomainEvent,
    GenerationCompleted,
    PipelineCompleted,
    PromptBuilt,
    RetrievalCompleted,
)
from mission_engine.events import (
    MissionApproved,
    MissionAwaitingApproval,
    MissionCancelled,
    MissionCompleted,
    MissionCreated,
    MissionFailed,
    MissionPlanned,
    MissionRejected,
    MissionResumed,
    MissionStepCompleted,
)

from mission_store.outbox_errors import OutboxError, UnsupportedEventType

# The serialization version of the JSON `payload` column. Bumped only when a persisted event shape
# changes; a forward-migration path ships with each bump (deferred until a version 2 exists).
CURRENT_OUTBOX_PAYLOAD_VERSION = 1

# The columns the sink writes, in a stable order. DB-managed columns (`id`, `created_at`,
# `published_at`) are deliberately absent — they belong to the database/relay, never the event.
OUTBOX_WRITE_COLUMNS: tuple[str, ...] = (
    "event_name",
    "trace_id",
    "tenant_id",
    "mission_id",
    "occurred_at",
    "payload",
    "payload_schema_version",
)

# Columns the relay reads back, in a stable order.
OUTBOX_READ_COLUMNS: tuple[str, ...] = ("id", *OUTBOX_WRITE_COLUMNS, "published_at")

# The one JSONB column. outbox.py wraps it for the driver; psycopg returns it parsed on read.
JSONB_COLUMNS: frozenset[str] = frozenset({"payload"})

# The name→class rehydration registry. Every concrete domain event the platform can emit is listed
# explicitly (no dynamic subclass discovery): the mission lifecycle events (ADR 0042) and the
# pipeline events (ADR 0039). A registry-completeness test guards against an emitted event type
# being forgotten here. An unregistered name fails loud as `UnsupportedEventType` (I8).
_REGISTERED_EVENTS: tuple[type[DomainEvent], ...] = (
    MissionCreated,
    MissionPlanned,
    MissionStepCompleted,
    MissionAwaitingApproval,
    MissionResumed,
    MissionApproved,
    MissionRejected,
    MissionCompleted,
    MissionFailed,
    MissionCancelled,
    RetrievalCompleted,
    PromptBuilt,
    GenerationCompleted,
    AnswerValidated,
    PipelineCompleted,
)

EVENT_REGISTRY: dict[str, type[DomainEvent]] = {cls.name: cls for cls in _REGISTERED_EVENTS}


@dataclass(frozen=True)
class OutboxRecord:
    """One outbox row as plain Python — what the relay reads before rehydrating the event."""

    id: int
    event_name: str
    trace_id: str
    tenant_id: str
    mission_id: str
    occurred_at: float
    payload: dict[str, Any]
    payload_schema_version: int
    published_at: Any = None  # DB timestamptz (or None); opaque to the relay's decision to publish


# --- write side: event → row ------------------------------------------------------------


def event_to_row(event: DomainEvent) -> dict[str, Any]:
    """The event as a plain outbox row (ADR 0043-S4 §8). `payload` is the event's canonical
    `to_dict()`; the denormalized columns mirror its stamp so the relay never opens the blob to
    order or dispatch. Values are JSON-plain; the sink wraps the JSONB column for the driver."""
    return {
        "event_name": event.name,
        "trace_id": event.trace_id,
        "tenant_id": event.tenant_id,
        "mission_id": event.mission_id,
        "occurred_at": event.occurred_at,
        "payload": event.to_dict(),
        "payload_schema_version": CURRENT_OUTBOX_PAYLOAD_VERSION,
    }


# --- read side: row → record → event ----------------------------------------------------


def record_from_row(row: dict[str, Any]) -> OutboxRecord:
    """A fetched DB row into an `OutboxRecord`. Pure — no driver, no rehydration yet."""
    return OutboxRecord(
        id=int(row["id"]),
        event_name=row["event_name"],
        trace_id=row["trace_id"],
        tenant_id=row["tenant_id"],
        mission_id=row["mission_id"],
        occurred_at=float(row["occurred_at"]),
        payload=row["payload"],
        payload_schema_version=int(
            row.get("payload_schema_version", CURRENT_OUTBOX_PAYLOAD_VERSION)
        ),
        published_at=row.get("published_at"),
    )


def event_from_record(record: OutboxRecord) -> DomainEvent:
    """Rebuild a typed `DomainEvent` from a stored record via the registry. An unregistered
    `event_name` raises `UnsupportedEventType` (no generic fallback, I8); an unknown payload version
    fails loud. The relay leaves such a row unpublished — it never deletes or marks it (§6)."""
    if record.payload_schema_version != CURRENT_OUTBOX_PAYLOAD_VERSION:
        raise OutboxError(
            f"outbox row {record.id} has payload_schema_version "
            f"{record.payload_schema_version}; this build reads version "
            f"{CURRENT_OUTBOX_PAYLOAD_VERSION} only"
        )
    event_cls = EVENT_REGISTRY.get(record.event_name)
    if event_cls is None:
        raise UnsupportedEventType(event_name=record.event_name, outbox_id=record.id)
    return _build_event(event_cls, record.payload)


def _build_event(event_cls: type[DomainEvent], payload: dict[str, Any]) -> DomainEvent:
    """Reconstruct the event from its `to_dict()` payload using the dataclass's own init fields.
    `name` is a ClassVar (not an init field) and is skipped; a tuple-typed field whose stored value
    is a JSON list is coerced back to a tuple so the rebuilt event is a faithful, typed copy."""
    kwargs: dict[str, Any] = {}
    for field in fields(event_cls):
        if field.name not in payload:
            continue
        value = payload[field.name]
        if isinstance(value, list) and isinstance(field.default, tuple):
            value = tuple(value)
        kwargs[field.name] = value
    return event_cls(**kwargs)
