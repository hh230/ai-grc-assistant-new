"""The Audit Sink terminal of the mission end-to-end path — Integration layer only.

The **Delivery Bus** (an `EventBus`, living *outside* the write transaction) carries the mission
events the `OutboxRelay` drains from the committed outbox. `MissionAuditSink` is the terminal
consumer this integration wiring subscribes there: it records every delivered `DomainEvent`, so an
end-to-end run can assert that exactly the committed-and-published events reached audit — the last
hop of

    Mission Engine → Store → Unit of Work → Outbox → Relay → Delivery Bus → **Audit Sink**

This is **glue, not a frozen component**: it lives entirely in the integration layer and changes
nothing in `event-bus`, `mission-engine`, or `mission-store`. It is deliberately minimal — a
faithful recorder of the mission event stream, not the pipeline-shaped `event_bus.AuditTrailBuilder`
(which finalizes an `AuditRecord` on `PipelineCompleted`, an event a *mission* run never emits — see
the integration report's architectural note). A durable, mission-shaped audit sink is a future
concern; this verifies delivery reaches audit, nothing more.
"""

from __future__ import annotations

from event_bus.events import DomainEvent


class MissionAuditSink:
    """Records every `DomainEvent` delivered onto the Delivery Bus. Subscribe `record` to the bus
    (`subscribe(ALL_EVENTS, sink.record)`); it appends in delivery order and never raises, so it is
    a safe terminal consumer. Query helpers scope the recorded stream to one mission for assertions.
    """

    def __init__(self) -> None:
        self.records: list[DomainEvent] = []

    def record(self, event: DomainEvent) -> None:
        """The `EventHandler` seam: capture one delivered event. No I/O, no filtering — every event
        the Delivery Bus dispatches is an event that was durably committed and published (I11)."""
        self.records.append(event)

    def events_for(self, mission_id: str) -> list[DomainEvent]:
        """The delivered events for one mission, in delivery order."""
        return [event for event in self.records if event.mission_id == mission_id]

    def event_names_for(self, mission_id: str) -> list[str]:
        """The delivered events' names for one mission, in delivery order — the shape most
        end-to-end assertions compare against (e.g. `["mission.created", "mission.completed"]`)."""
        return [event.name for event in self.events_for(mission_id)]

    def __len__(self) -> int:
        return len(self.records)
