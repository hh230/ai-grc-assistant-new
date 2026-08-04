"""The Outbox Relay process — the half of the Transactional Outbox that was missing.

Every mission write already captures its events into the outbox atomically with the state change
(ADR 0043, `OutboxSink`). Nothing ever drained them. Without a drain there is no Outbox *Pattern*,
only an outbox *table*: events accumulate, are never delivered, and the at-least-once guarantee the
ADR claims is not in force. The table also grows without bound, which is the slow path to a
read-only database.

`OutboxRelay.drain` — the mechanism — already existed and was tested. What did not exist is a
**process that runs it** and a **subscriber that receives what it publishes**. This module is both.

Deliberately a SEPARATE PROCESS, not a background thread in the API:

- The API's workers must stay free to serve requests. Draining inside a request path would make
  delivery latency a function of traffic, and traffic a function of delivery.
- Draining is single-writer by design (the frozen relay has no `FOR UPDATE SKIP LOCKED` — Rev.3
  defers multi-worker). One relay process is a structural guarantee of that; N API workers each
  draining would violate it silently.
- It can be restarted, scaled to zero, or paused without touching the API.

Run it as a second command on the same image:

    python -m grc_api.relay

**Head-of-line blocking is treated as an incident, not skipped.** `drain` publishes in insertion
order and leaves an unpublishable row unpublished (I8). If a row cannot be decoded, every event
behind it is stuck. The correct response is to stop and be loud — skipping the row would silently
break the ordering and at-least-once guarantees the outbox exists to provide.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from types import FrameType
from typing import Any

from event_bus.events import DomainEvent
from mission_store import OutboxRelay
from mission_store.outbox_errors import UnsupportedEventType

from grc_api.composition import database_dsn

logger = logging.getLogger("grc_api.relay")

DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_BATCH_LIMIT = 100
# Backoff after a database error, so a Postgres outage does not become a hot loop that hammers a
# database already in trouble.
ERROR_BACKOFF_SECONDS = 10.0


class StructuredLogPublisher:
    """Delivers each event as one structured log line — the audit stream.

    This is a REAL consumer, not a placeholder. CLAUDE.md §19 requires a tamper-evident,
    tenant-scoped, append-only audit trail suitable for external review; today these events exist
    only as rows inside the mission database and are visible nowhere else. Emitting them to the
    platform's log stream makes the trail exist outside the table that produced it, which is the
    property an auditor actually needs.

    It is also the seam: when a broker (Kafka/NATS — CLAUDE.md §4 "target") arrives, it replaces
    this publisher and nothing else changes. That is why the relay depends on `OutboxPublisher`
    and not on this class.
    """

    def publish(self, event: DomainEvent) -> None:
        logger.info(
            json.dumps(
                {
                    "stream": "audit",
                    "event": event.name,
                    "tenant_id": event.tenant_id,
                    "mission_id": event.mission_id,
                    "trace_id": event.trace_id,
                    "occurred_at": event.occurred_at,
                },
                sort_keys=True,
            )
        )


@dataclass
class RelayStats:
    """What one run produced — returned rather than logged, so a test can assert on it."""

    cycles: int = 0
    published: int = 0
    errors: int = 0
    blocked: bool = False
    blocking_reason: str = ""


@dataclass
class _Shutdown:
    """Graceful stop. A deploy sends SIGTERM; finishing the current cycle rather than dying
    mid-drain avoids re-publishing a batch that was already delivered but not yet marked."""

    requested: bool = field(default=False)

    def request(self, _signum: int, _frame: FrameType | None) -> None:
        self.requested = True
        logger.info(json.dumps({"stream": "relay", "event": "shutdown_requested"}))


def run_relay(
    relay: OutboxRelay,
    publisher: Any,
    *,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    limit: int = DEFAULT_BATCH_LIMIT,
    max_cycles: int | None = None,
    sleep: Any = time.sleep,
    shutdown: _Shutdown | None = None,
) -> RelayStats:
    """Drain until told to stop.

    `max_cycles` bounds the loop for tests and for a one-shot drain; production passes None and
    relies on the shutdown signal.
    """
    stats = RelayStats()
    shutdown = shutdown or _Shutdown()

    while not shutdown.requested:
        if max_cycles is not None and stats.cycles >= max_cycles:
            break
        stats.cycles += 1

        try:
            delivered = relay.drain(publisher, limit=limit)
        except UnsupportedEventType as exc:
            # Every event behind this row is now stuck. Skipping it would silently break ordering
            # and the at-least-once guarantee, so the relay stops and says so — loudly enough that
            # monitoring turns it into a page rather than a mystery.
            stats.blocked = True
            stats.blocking_reason = str(exc)
            logger.critical(
                json.dumps(
                    {
                        "stream": "relay",
                        "event": "outbox_blocked",
                        "reason": str(exc),
                        # Both carried by the exception: the row a human must triage, and the type
                        # a build must register. Without them the alert says "stuck" and nothing
                        # more, which is an alert nobody can act on.
                        "event_name": exc.event_name,
                        "outbox_id": exc.outbox_id,
                        "remediation": (
                            "an outbox row holds an event type this build cannot decode. Delivery "
                            "is STOPPED and every later event is queued behind it. Deploy a build "
                            "that registers the type, or triage the row by hand."
                        ),
                    }
                )
            )
            return stats
        except Exception as exc:  # noqa: BLE001 — DB down, connection reset, read-only
            stats.errors += 1
            logger.error(
                json.dumps(
                    {"stream": "relay", "event": "drain_failed", "error": f"{type(exc).__name__}: {exc}"}
                )
            )
            sleep(ERROR_BACKOFF_SECONDS)
            continue

        stats.published += delivered
        # Only idle when there was nothing to do. A full batch means more is waiting, so drain
        # again immediately rather than sleeping through a backlog.
        if delivered < limit:
            sleep(interval_seconds)

    return stats


def main(argv: list[str] | None = None) -> int:
    """Entry point: `python -m grc_api.relay`."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(message)s",  # the payload is already JSON; no second layer of formatting
        stream=sys.stdout,
    )
    argv = sys.argv[1:] if argv is None else argv
    once = "--once" in argv

    shutdown = _Shutdown()
    signal.signal(signal.SIGTERM, shutdown.request)
    signal.signal(signal.SIGINT, shutdown.request)

    relay = OutboxRelay(dsn=database_dsn())
    logger.info(json.dumps({"stream": "relay", "event": "started", "once": once}))
    try:
        stats = run_relay(
            relay,
            StructuredLogPublisher(),
            max_cycles=1 if once else None,
            shutdown=shutdown,
        )
    finally:
        relay.close()

    logger.info(
        json.dumps(
            {
                "stream": "relay",
                "event": "stopped",
                "cycles": stats.cycles,
                "published": stats.published,
                "errors": stats.errors,
                "blocked": stats.blocked,
            }
        )
    )
    # A blocked outbox exits non-zero so a platform's restart policy and any alert on exit code
    # both see it. Restarting will not clear it — that is the point: it needs a human.
    return 1 if stats.blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
