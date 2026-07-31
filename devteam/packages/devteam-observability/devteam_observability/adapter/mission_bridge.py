"""``MissionEventBridge`` — restates the Core's mission lifecycle events for the runtime view.

The frozen Mission Engine already emits the lifecycle facts (``mission.created`` ... ``completed`` /
``failed`` / ``awaiting_approval`` / ``approved`` / ``rejected``) onto the Event Bus (ADR 0042 §8).
This bridge subscribes there and maps each to a roster-neutral ``MissionObserved`` — it does NOT
re-emit or duplicate the Core events, and it adds no transport. That is why the observability layer
does not re-invent mission events: it reuses the engine's, and only *adds* the agent-level ones the
Core never had.

Subscribe ``record`` to ``ALL_EVENTS``; non-mission events (e.g. a product pipeline's) are ignored.
"""

from __future__ import annotations

from event_bus import ALL_EVENTS
from event_bus.bus import EventBus
from event_bus.events import DomainEvent
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

from devteam_observability.core import MissionEventKind, MissionObserved, RuntimeObserver

# Exact-type map from a Core mission event to the roster-neutral kind. Exact ``type(event)`` (not
# isinstance) so the ``MissionEvent`` base and future siblings never match by accident.
_KIND_BY_EVENT: dict[type[DomainEvent], MissionEventKind] = {
    MissionCreated: MissionEventKind.CREATED,
    MissionPlanned: MissionEventKind.PLANNED,
    MissionStepCompleted: MissionEventKind.STEP_COMPLETED,
    MissionAwaitingApproval: MissionEventKind.AWAITING_APPROVAL,
    MissionResumed: MissionEventKind.RESUMED,
    MissionApproved: MissionEventKind.APPROVED,
    MissionRejected: MissionEventKind.REJECTED,
    MissionCompleted: MissionEventKind.COMPLETED,
    MissionFailed: MissionEventKind.FAILED,
    MissionCancelled: MissionEventKind.CANCELLED,
}


class MissionEventBridge:
    """Maps Core mission events to ``MissionObserved`` on the observer. Construct with the observer
    the runtime feeds; call ``subscribe(bus)`` to wire it to the Event Bus."""

    def __init__(self, observer: RuntimeObserver) -> None:
        self._observer = observer

    def subscribe(self, bus: EventBus) -> None:
        bus.subscribe(ALL_EVENTS, self.record)

    def record(self, event: DomainEvent) -> None:
        kind = _KIND_BY_EVENT.get(type(event))
        if kind is None:
            return  # not a mission lifecycle event — leave it to whoever cares
        self._observer.observe(
            MissionObserved(
                mission_id=event.mission_id,
                tenant_id=event.tenant_id,
                occurred_at=event.occurred_at,
                kind=kind,
                step_id=str(getattr(event, "step_id", "")),
                detail=_detail(event),
            )
        )


def _detail(event: DomainEvent) -> str:
    """A short human-facing note for the event feed, pulled from whichever summary field the Core
    event carries — never the plan text or a step's output (the bus stays a thin notification)."""
    for field_name in ("goal", "reason", "comment"):
        value = getattr(event, field_name, "")
        if value:
            return str(value)
    step_count = getattr(event, "step_count", 0)
    return f"{step_count} step(s)" if step_count else ""
