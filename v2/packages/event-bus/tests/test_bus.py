"""The in-process dispatcher: synchronous, ordered, type-scoped, with handler isolation."""

from __future__ import annotations

import pytest
from event_bus import (
    ALL_EVENTS,
    DomainEvent,
    EventBus,
    GenerationCompleted,
    InProcessEventBus,
    PromptBuilt,
    RecordingEventBus,
)


def test_in_process_bus_satisfies_the_port():
    assert isinstance(InProcessEventBus(), EventBus)
    assert isinstance(RecordingEventBus(), EventBus)


def test_publish_dispatches_to_type_specific_subscriber():
    bus = InProcessEventBus()
    seen: list[DomainEvent] = []
    bus.subscribe(GenerationCompleted, seen.append)
    bus.publish(GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1", provider="openai"))
    bus.publish(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))  # different type — not delivered
    assert len(seen) == 1
    assert isinstance(seen[0], GenerationCompleted)


def test_subscribe_all_receives_every_event():
    bus = InProcessEventBus()
    seen: list[str] = []
    bus.subscribe_all(lambda e: seen.append(e.name))
    bus.publish(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))
    bus.publish(GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))
    assert seen == ["prompt.built", "generation.completed"]


def test_dispatch_is_synchronous_and_in_registration_order():
    bus = InProcessEventBus()
    order: list[str] = []
    bus.subscribe(PromptBuilt, lambda e: order.append("first"))
    bus.subscribe(PromptBuilt, lambda e: order.append("second"))
    bus.subscribe_all(lambda e: order.append("wildcard"))
    bus.publish(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))
    # type handlers before wildcard, each in registration order — and already complete
    assert order == ["first", "second", "wildcard"]


def test_handler_error_propagates_by_default():
    bus = InProcessEventBus()
    bus.subscribe_all(_boom)
    with pytest.raises(RuntimeError, match="handler failed"):
        bus.publish(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))


def test_error_handler_isolates_failures_and_continues():
    captured: list[tuple[str, str]] = []
    bus = InProcessEventBus(error_handler=lambda e, exc: captured.append((e.name, str(exc))))
    reached: list[str] = []
    bus.subscribe_all(_boom)
    bus.subscribe_all(lambda e: reached.append(e.name))  # must still run
    bus.publish(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))
    assert reached == ["prompt.built"]
    assert captured == [("prompt.built", "handler failed")]


def test_no_subscribers_is_a_no_op():
    InProcessEventBus().publish(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))  # must not raise


def test_recording_bus_captures_without_dispatch():
    bus = RecordingEventBus()
    bus.subscribe(ALL_EVENTS, _boom)  # accepted but never called
    bus.publish(PromptBuilt(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))
    assert [e.name for e in bus.events] == ["prompt.built"]


def test_subscribe_by_name_string_works():
    bus = InProcessEventBus()
    seen: list[str] = []
    bus.subscribe(ALL_EVENTS, lambda e: seen.append(e.name))
    bus.publish(GenerationCompleted(trace_id="t", tenant_id="org_acme", mission_id="mis_1"))
    assert seen == ["generation.completed"]


def _boom(event: DomainEvent) -> None:
    raise RuntimeError("handler failed")
