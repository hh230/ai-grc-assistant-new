"""Exercise the outbox's query-construction paths **without a live database**, with recording fakes:
the sink's INSERT shape (columns, JSONB wrapping, and that the sink never commits — I3), and the
relay's unpublished-select / publish-in-order / mark-published path, including that an unregistered
event raises and leaves its row (and the ones after it) unmarked (I8, §6).
"""

from __future__ import annotations

import pytest

psycopg = pytest.importorskip("psycopg")  # the sink wraps the payload via psycopg's JSONB adapter

from event_bus.events import DomainEvent  # noqa: E402
from mission_engine.events import MissionCreated, MissionPlanned  # noqa: E402
from mission_store import OutboxRelay, OutboxSink, UnsupportedEventType  # noqa: E402
from mission_store.outbox_codec import OUTBOX_WRITE_COLUMNS, event_to_row  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402


class _RecordingCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.executed: list[tuple[str, object]] = []

    def __enter__(self) -> _RecordingCursor:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def execute(self, sql: str, params: object = None) -> _RecordingCursor:
        self.executed.append((sql, params))
        return self

    def fetchall(self) -> list[dict]:
        return list(self._rows)


class _RecordingConnection:
    """Records writes and hands back canned rows to the relay's cursor — the outbox with no DB."""

    def __init__(self, *, rows: list[dict] | None = None) -> None:
        self._rows = rows or []
        self.writes: list[tuple[str, dict]] = []
        self.commits = 0
        self.cursors: list[_RecordingCursor] = []

    def execute(self, sql: str, params: dict | None = None):
        self.writes.append((sql, params or {}))
        return type("R", (), {"rowcount": 1})()

    def cursor(self, row_factory=None) -> _RecordingCursor:
        cur = _RecordingCursor(list(self._rows))
        self.cursors.append(cur)
        return cur

    def commit(self) -> None:  # present so a stray commit would be *detectable*, not an error
        self.commits += 1


class _RecordingPublisher:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.published.append(event)


def _read_row(event, *, id: int, published_at=None) -> dict:
    row = dict(event_to_row(event))
    row["id"] = id
    row["published_at"] = published_at
    return row


# ── sink: INSERT shape, JSONB wrapping, and NO commit (I3) ────────────────────
def test_sink_write_builds_insert_and_wraps_payload_and_does_not_commit() -> None:
    conn = _RecordingConnection()
    event = MissionCreated(
        trace_id="trc", tenant_id="org_acme", mission_id="mis_1", occurred_at=1.0, goal="g"
    )
    OutboxSink(connection=conn, table="outbox").write(event)

    sql, params = conn.writes[0]
    assert "INSERT INTO outbox" in sql
    assert set(params.keys()) == set(OUTBOX_WRITE_COLUMNS)
    assert params["event_name"] == "mission.created"
    assert params["tenant_id"] == "org_acme"
    assert isinstance(params["payload"], Jsonb)  # the one JSONB column is wrapped
    assert not isinstance(params["event_name"], Jsonb)
    assert conn.commits == 0  # the sink never commits — the UnitOfWork owns the transaction (I3)


# ── relay: select unpublished, publish in order, mark each published ──────────
def test_relay_publishes_unpublished_rows_in_order_and_marks_them() -> None:
    rows = [
        _read_row(
            MissionCreated(trace_id="t", tenant_id="o", mission_id="m", occurred_at=1.0), id=1
        ),
        _read_row(
            MissionPlanned(trace_id="t", tenant_id="o", mission_id="m", occurred_at=2.0), id=2
        ),
    ]
    conn = _RecordingConnection(rows=rows)
    publisher = _RecordingPublisher()

    count = OutboxRelay(connection=conn, table="outbox").drain(publisher)

    assert count == 2
    # the read is scoped to unpublished rows, in insertion order (I7)
    select_sql, _ = conn.cursors[0].executed[0]
    assert "WHERE published_at IS NULL ORDER BY id" in select_sql
    assert [e.name for e in publisher.published] == ["mission.created", "mission.planned"]
    # each delivered row is marked published, by id
    marks = [(sql, params) for sql, params in conn.writes if "SET published_at = now()" in sql]
    assert [params["id"] for _sql, params in marks] == [1, 2]


def test_relay_leaves_unregistered_row_unpublished_and_raises() -> None:
    good = _read_row(
        MissionCreated(trace_id="t", tenant_id="o", mission_id="m", occurred_at=1.0), id=1
    )
    poison = _read_row(
        MissionCreated(trace_id="t", tenant_id="o", mission_id="m", occurred_at=2.0), id=2
    )
    poison["event_name"] = "mystery.event"
    poison["payload"] = {"name": "mystery.event"}
    conn = _RecordingConnection(rows=[good, poison])
    publisher = _RecordingPublisher()

    with pytest.raises(UnsupportedEventType) as exc_info:
        OutboxRelay(connection=conn, table="outbox").drain(publisher)

    assert exc_info.value.event_name == "mystery.event"
    # the good row before it was published+marked; the poison row is neither published nor marked
    assert [e.name for e in publisher.published] == ["mission.created"]
    marked_ids = [params["id"] for sql, params in conn.writes if "SET published_at" in sql]
    assert marked_ids == [1]  # id=2 (poison) left unpublished (I8, §6)
