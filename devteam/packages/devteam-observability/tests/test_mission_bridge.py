"""The mission bridge: Core lifecycle events become MissionObserved, nothing is duplicated."""

from __future__ import annotations

from devteam_observability import AgentRuntimeRegistry, MissionEventBridge, MissionEventKind
from event_bus import InProcessEventBus
from event_bus.events import RetrievalCompleted
from mission_engine.events import (
    MissionAwaitingApproval,
    MissionCompleted,
    MissionCreated,
    MissionFailed,
)


def _bus_and_registry() -> tuple[InProcessEventBus, AgentRuntimeRegistry]:
    registry = AgentRuntimeRegistry()
    bus = InProcessEventBus()
    MissionEventBridge(registry).subscribe(bus)
    return bus, registry


def test_created_then_completed_is_folded_into_mission_state() -> None:
    bus, registry = _bus_and_registry()
    bus.publish(MissionCreated(trace_id="t", tenant_id="platform", mission_id="m1", goal="review"))
    bus.publish(MissionCompleted(trace_id="t", tenant_id="platform", mission_id="m1", step_count=2))
    mission = registry.mission_state("m1")
    assert mission is not None
    assert mission.status is MissionEventKind.COMPLETED


def test_awaiting_approval_is_mapped_to_the_approval_kind() -> None:
    bus, registry = _bus_and_registry()
    bus.publish(
        MissionAwaitingApproval(trace_id="t", tenant_id="platform", mission_id="m1", step_id="s1")
    )
    mission = registry.mission_state("m1")
    assert mission is not None
    assert mission.status is MissionEventKind.AWAITING_APPROVAL


def test_failure_detail_is_carried_onto_the_feed() -> None:
    bus, registry = _bus_and_registry()
    bus.publish(
        MissionFailed(trace_id="t", tenant_id="platform", mission_id="m1", reason="step s1 failed")
    )
    events = registry.recent_events()
    assert len(events) == 1
    assert events[0].to_dict()["detail"] == "step s1 failed"


def test_a_non_mission_event_is_ignored() -> None:
    bus, registry = _bus_and_registry()
    # A pipeline event travels the same bus; the bridge maps only mission lifecycle events, so it
    # leaves this one alone — nothing is folded, no mission state appears.
    bus.publish(RetrievalCompleted(trace_id="t", tenant_id="platform", mission_id="m1", results=3))
    assert registry.all_missions() == []
    assert registry.recent_events() == []
