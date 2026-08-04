"""Tests for the Outbox Relay process (B1).

The relay MECHANISM (`OutboxRelay.drain`) is already tested in `mission-store`. What is tested here
is the process around it: that it keeps draining, that it stops when told, that a database outage
does not become a hot loop, and — most importantly — that an undecodable row stops delivery loudly
instead of being skipped.
"""

from __future__ import annotations

from typing import Any

import pytest
from event_bus.events import DomainEvent
from mission_store.outbox_errors import UnsupportedEventType

from grc_api.relay import RelayStats, StructuredLogPublisher, _Shutdown, run_relay


class _Relay:
    """A stand-in for the real relay: returns a scripted sequence of batch sizes, or raises."""

    def __init__(self, script: list[Any]) -> None:
        self._script = script
        self.calls = 0

    def drain(self, publisher: Any, *, limit: int = 100) -> int:
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return int(outcome)


def _no_sleep(_seconds: float) -> None:
    return None


# --- draining --------------------------------------------------------------------------------


def test_it_keeps_draining_until_stopped() -> None:
    relay = _Relay([5, 3, 0])
    stats = run_relay(relay, StructuredLogPublisher(), max_cycles=3, sleep=_no_sleep)
    assert stats.cycles == 3
    assert stats.published == 8


def test_a_full_batch_drains_again_immediately_instead_of_sleeping() -> None:
    """Sleeping through a backlog would make delivery latency grow with the size of the backlog —
    exactly when it matters least to be slow."""
    slept: list[float] = []
    relay = _Relay([100, 100, 0])
    run_relay(
        relay, StructuredLogPublisher(), limit=100, max_cycles=3, sleep=slept.append
    )
    # Only the final, partial batch idles.
    assert slept == [pytest.approx(2.0)]


def test_shutdown_is_honoured_between_cycles() -> None:
    """A deploy sends SIGTERM. Stopping between cycles rather than mid-drain avoids re-publishing a
    batch that was delivered but not yet marked."""
    shutdown = _Shutdown()
    shutdown.request(15, None)
    stats = run_relay(_Relay([10]), StructuredLogPublisher(), shutdown=shutdown, sleep=_no_sleep)
    assert stats.cycles == 0, "a requested shutdown must stop before starting more work"


# --- the failure that matters most -------------------------------------------------------------


def test_an_undecodable_row_stops_delivery_loudly_instead_of_being_skipped() -> None:
    """`drain` publishes in insertion order and leaves an unpublishable row unpublished (I8), so
    every event behind it is stuck. Skipping it would silently break both ordering and the
    at-least-once guarantee the outbox exists to provide — so the relay stops and reports."""
    relay = _Relay([UnsupportedEventType(event_name="MissionTeleported", outbox_id=42)])
    stats = run_relay(relay, StructuredLogPublisher(), max_cycles=5, sleep=_no_sleep)

    assert stats.blocked
    assert "MissionTeleported" in stats.blocking_reason
    # The row id must survive into the report: an alert saying only "stuck" cannot be acted on.
    assert "42" in stats.blocking_reason
    assert relay.calls == 1, "it must not keep retrying a row that cannot succeed"


def test_a_blocked_outbox_is_visible_in_the_stats_not_only_in_a_log() -> None:
    """A gate or a test must be able to see it without scraping log text."""
    stats = run_relay(
        _Relay([UnsupportedEventType(event_name="Unknown", outbox_id=7)]),
        StructuredLogPublisher(),
        max_cycles=1,
        sleep=_no_sleep,
    )
    assert isinstance(stats, RelayStats)
    assert stats.blocked is True


# --- database trouble ------------------------------------------------------------------------


def test_a_database_error_backs_off_rather_than_hot_looping() -> None:
    """A Postgres outage must not turn the relay into a load generator against a database that is
    already in trouble."""
    slept: list[float] = []
    relay = _Relay([RuntimeError("connection reset"), 0])
    stats = run_relay(relay, StructuredLogPublisher(), max_cycles=2, sleep=slept.append)

    assert stats.errors == 1
    assert slept[0] == pytest.approx(10.0), "the first sleep must be the error backoff"


def test_a_database_error_does_not_stop_the_relay() -> None:
    """Transient failures are normal. Only an undecodable row is terminal."""
    relay = _Relay([RuntimeError("temporary"), 4, 0])
    stats = run_relay(relay, StructuredLogPublisher(), max_cycles=3, sleep=_no_sleep)
    assert not stats.blocked
    assert stats.published == 4


# --- the delivery side ------------------------------------------------------------------------


def test_every_delivered_event_carries_its_tenant_and_mission(caplog: Any) -> None:
    """An audit line without a tenant is not auditable. Both are on the event base class precisely
    so this is structurally impossible to omit (ADR 0040 §6)."""
    event = DomainEvent(trace_id="t-1", tenant_id="tenant-9", mission_id="m-3")
    with caplog.at_level("INFO", logger="grc_api.relay"):
        StructuredLogPublisher().publish(event)

    line = caplog.records[-1].message
    assert '"tenant_id": "tenant-9"' in line
    assert '"mission_id": "m-3"' in line
    assert '"stream": "audit"' in line
