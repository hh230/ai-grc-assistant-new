"""The observer port: fan-out to several consumers, fail-safe isolation."""

from __future__ import annotations

import pytest
from devteam_observability import (
    AgentId,
    AgentStarted,
    AgentSubsystem,
    CompositeObserver,
    RuntimeEvent,
)

QA = AgentId(AgentSubsystem.PLATFORM, "qa")


class _Recorder:
    def __init__(self) -> None:
        self.count = 0

    def observe(self, event: RuntimeEvent) -> None:
        self.count += 1


class _Broken:
    def observe(self, event: RuntimeEvent) -> None:
        raise RuntimeError("bad observer")


def test_composite_fans_one_event_out_to_every_observer() -> None:
    a, b = _Recorder(), _Recorder()
    composite = CompositeObserver([a, b])
    composite.observe(AgentStarted(mission_id="m1", agent=QA, occurred_at=1.0))
    assert a.count == 1
    assert b.count == 1


def test_a_broken_observer_is_isolated_when_an_error_handler_is_given() -> None:
    seen: list[Exception] = []
    good = _Recorder()
    composite = CompositeObserver(
        [_Broken(), good], error_handler=lambda _event, exc: seen.append(exc)
    )
    composite.observe(AgentStarted(mission_id="m1", agent=QA, occurred_at=1.0))
    assert good.count == 1  # dispatch continued past the broken one
    assert len(seen) == 1


def test_without_an_error_handler_a_broken_observer_raises_loudly() -> None:
    composite = CompositeObserver([_Broken()])
    with pytest.raises(RuntimeError):
        composite.observe(AgentStarted(mission_id="m1", agent=QA, occurred_at=1.0))
