"""Adapters (ADR 0065) — hot-swappable event sources; adapters only produce events.

Rule 1: register adapters, drain them all (no if/else). Rule 3: a failing adapter is contained.
Rule 5: an adapter's whole surface is ``drain`` → events; it never touches the coordinator or state.
"""

from __future__ import annotations

from devteam_organization.lifecycle import (
    AdapterRegistry,
    LifecycleEvent,
    LifecycleEventKind,
    Trigger,
)


class _FakeAdapter:
    def __init__(self, adapter_id: str, trigger: Trigger, events: list[LifecycleEvent]) -> None:
        self._id = adapter_id
        self._trigger = trigger
        self._events = list(events)
        self.fail = False

    @property
    def id(self) -> str:
        return self._id

    @property
    def trigger(self) -> Trigger:
        return self._trigger

    def drain(self) -> list[LifecycleEvent]:
        if self.fail:
            raise RuntimeError("boom")
        drained, self._events = self._events, []
        return drained


def _event(
    kind: LifecycleEventKind, event_id: str, source: str, trigger: Trigger
) -> LifecycleEvent:
    return LifecycleEvent(kind, event_id, "ref-1", trigger, source=source)


def test_registry_drains_every_registered_adapter() -> None:
    registry = AdapterRegistry()
    gh = _FakeAdapter(
        "github-actions",
        Trigger.GITHUB,
        [_event(LifecycleEventKind.EXECUTION_FINISHED, "g1", "github-actions", Trigger.GITHUB)],
    )
    web = _FakeAdapter(
        "website-connector",
        Trigger.CONNECTOR,
        [_event(LifecycleEventKind.EVIDENCE_CHANGED, "w1", "website-connector", Trigger.CONNECTOR)],
    )
    registry.register(gh)
    registry.register(web)

    drained = registry.drain_all()
    assert {e.event_id for e in drained} == {"g1", "w1"}  # both sources, no if/else
    assert registry.drain_all() == []  # drained once — buffers are now empty
    assert {a.id for a in registry.adapters()} == {"github-actions", "website-connector"}


def test_get_returns_the_adapter_or_none() -> None:
    registry = AdapterRegistry()
    adapter = _FakeAdapter("jenkins", Trigger.GITHUB, [])
    registry.register(adapter)
    assert registry.get("jenkins") is adapter
    assert registry.get("gitlab") is None  # a new source is just a registration away


def test_a_failing_adapter_is_contained() -> None:
    registry = AdapterRegistry()
    broken = _FakeAdapter("broken", Trigger.RUNTIME, [])
    broken.fail = True
    healthy = _FakeAdapter(
        "healthy",
        Trigger.CONNECTOR,
        [_event(LifecycleEventKind.EVIDENCE_CHANGED, "h1", "healthy", Trigger.CONNECTOR)],
    )
    registry.register(broken)
    registry.register(healthy)

    drained = registry.drain_all()  # the broken adapter must not stall the healthy one (rule 3)
    assert [e.event_id for e in drained] == ["h1"]
