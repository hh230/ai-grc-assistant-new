"""Pure outbox-codec tests (no database): event → row denormalization, the row → typed-event
round-trip through the rehydration registry, registry completeness, and the fail-loud paths
(`UnsupportedEventType` for an unregistered name, `OutboxError` for an unknown payload version).
"""

from __future__ import annotations

import inspect

import pytest
from event_bus.events import RetrievalCompleted
from mission_engine import events as mission_events
from mission_engine.events import MissionCreated, MissionStepCompleted
from mission_store.outbox_codec import (
    CURRENT_OUTBOX_PAYLOAD_VERSION,
    EVENT_REGISTRY,
    OUTBOX_WRITE_COLUMNS,
    event_from_record,
    event_to_row,
    record_from_row,
)
from mission_store.outbox_errors import OutboxError, UnsupportedEventType


def _read_row(event, *, id: int = 1, published_at=None) -> dict:
    """The shape the relay reads back: the written columns plus the DB-managed id/published_at."""
    row = dict(event_to_row(event))
    row["id"] = id
    row["published_at"] = published_at
    return row


def test_event_to_row_denormalizes_and_carries_full_payload() -> None:
    event = MissionCreated(
        trace_id="trc_1", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.5, goal="do x"
    )
    row = event_to_row(event)
    assert set(row.keys()) == set(OUTBOX_WRITE_COLUMNS)
    assert row["event_name"] == "mission.created"
    assert row["trace_id"] == "trc_1"
    assert row["tenant_id"] == "org_acme"
    assert row["mission_id"] == "mis_1"
    assert row["occurred_at"] == 1.5
    assert row["payload_schema_version"] == CURRENT_OUTBOX_PAYLOAD_VERSION
    assert row["payload"] == event.to_dict()  # the whole canonical event


def test_round_trip_rebuilds_the_same_typed_event() -> None:
    event = MissionCreated(
        trace_id="trc_1", tenant_id="org_acme", mission_id="mis_1", occurred_at=2.0, goal="draft"
    )
    rebuilt = event_from_record(record_from_row(_read_row(event)))
    assert type(rebuilt) is MissionCreated
    assert rebuilt.to_dict() == event.to_dict()


def test_round_trip_preserves_tuple_typed_fields() -> None:
    event = MissionStepCompleted(
        trace_id="trc_1",
        tenant_id="org_acme",
        mission_id="mis_1",
        occurred_at=3.0,
        step_id="stp_1",
        ok=True,
        source_ids=("src_a", "src_b"),
    )
    rebuilt = event_from_record(record_from_row(_read_row(event)))
    assert type(rebuilt) is MissionStepCompleted
    assert rebuilt.source_ids == ("src_a", "src_b")  # list-in-JSON coerced back to a tuple
    assert isinstance(rebuilt.source_ids, tuple)
    assert rebuilt.to_dict() == event.to_dict()


def test_round_trip_pipeline_event_across_packages() -> None:
    """A non-mission `DomainEvent` (pipeline, ADR 0039) rehydrates through the same registry."""
    event = RetrievalCompleted(
        trace_id="trc_1", tenant_id="org_acme", mission_id="mis_1", occurred_at=4.0, results=3
    )
    rebuilt = event_from_record(record_from_row(_read_row(event)))
    assert type(rebuilt) is RetrievalCompleted
    assert rebuilt.to_dict() == event.to_dict()


def test_round_trip_rebuilds_the_approval_decision_events() -> None:
    """The two ADR 0044 Slice 2 decision events round-trip through the same outbox registry as every
    other mission event — carrying their approval id, approver, and (for reject) the comment."""
    from mission_engine.events import MissionApproved, MissionRejected

    approved = MissionApproved(
        trace_id="trc_1",
        tenant_id="org_acme",
        mission_id="mis_1",
        occurred_at=5.0,
        approval_id="apr_1",
        approver="u_owner",
    )
    rejected = MissionRejected(
        trace_id="trc_1",
        tenant_id="org_acme",
        mission_id="mis_1",
        occurred_at=7.0,
        approval_id="apr_1",
        approver="u_owner",
        comment="insufficient evidence",
    )
    for event in (approved, rejected):
        rebuilt = event_from_record(record_from_row(_read_row(event)))
        assert type(rebuilt) is type(event)
        assert rebuilt.to_dict() == event.to_dict()


def test_registry_covers_every_mission_event_type() -> None:
    """Completeness guard: every concrete `MissionEvent` subclass must be registered, so a newly
    added mission event cannot be silently forgotten (which would fail loud at drain, I8)."""
    concrete = [
        cls
        for _, cls in inspect.getmembers(mission_events, inspect.isclass)
        if issubclass(cls, mission_events.MissionEvent) and cls is not mission_events.MissionEvent
    ]
    assert concrete  # sanity: we actually found some
    for cls in concrete:
        assert EVENT_REGISTRY.get(cls.name) is cls, f"{cls.__name__} ({cls.name}) is not registered"


def test_unregistered_event_name_raises_unsupported_event_type() -> None:
    row = _read_row(
        MissionCreated(trace_id="t", tenant_id="org", mission_id="m", occurred_at=1.0), id=7
    )
    row["event_name"] = "mystery.event"
    row["payload"] = {"name": "mystery.event"}
    with pytest.raises(UnsupportedEventType) as exc_info:
        event_from_record(record_from_row(row))
    assert exc_info.value.event_name == "mystery.event"
    assert exc_info.value.outbox_id == 7


def test_unknown_payload_version_fails_loud() -> None:
    row = _read_row(
        MissionCreated(trace_id="t", tenant_id="org", mission_id="m", occurred_at=1.0), id=9
    )
    row["payload_schema_version"] = 999
    with pytest.raises(OutboxError):
        event_from_record(record_from_row(row))
