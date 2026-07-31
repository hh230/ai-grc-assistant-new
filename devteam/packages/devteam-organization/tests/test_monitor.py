"""The organization Worker — continuous operation: drain intents, supervise, heartbeat, loop."""

from __future__ import annotations

import pytest
from devteam_organization import (
    OrganizationMonitor,
    OrganizationRuntime,
    QueueIntentSource,
    Supervisor,
)
from devteam_organization.connectors import ConnectorConfig, build_registry
from devteam_organization.lifecycle_host import build_organization_lifecycle
from mission_engine.lifecycle import MissionStatus


def test_tick_syncs_the_lifecycle_and_stays_idle_without_evidence(
    runtime: OrganizationRuntime,
) -> None:
    config = ConnectorConfig()
    registry = build_registry(config, view_provider=lambda: runtime.view)
    lifecycle = build_organization_lifecycle(runtime, registry)
    outcome = OrganizationMonitor(runtime, Supervisor(runtime), lifecycle=lifecycle).tick()
    assert outcome.synced is True  # the lifecycle is the single operational path in the tick
    # Every connector is Unavailable (empty config) → no evidence → no fabricated problems.
    assert lifecycle.coordinator.states() == {}
    assert lifecycle.metrics_snapshot().active_problems == 0


def test_a_tick_runs_intents_supervises_and_heartbeats(runtime: OrganizationRuntime) -> None:
    monitor = OrganizationMonitor(
        runtime,
        Supervisor(runtime),
        intents=QueueIntentSource(["Draft a GDPR data-retention policy"]),
    )
    outcome = monitor.tick()
    assert len(outcome.missions) == 1
    assert outcome.missions[0].status is MissionStatus.COMPLETED
    assert outcome.supervision.healthy
    assert outcome.heartbeat is not None
    assert outcome.heartbeat.status is MissionStatus.COMPLETED


def test_a_tick_with_no_intents_still_heartbeats(runtime: OrganizationRuntime) -> None:
    outcome = OrganizationMonitor(runtime, Supervisor(runtime)).tick()
    assert outcome.missions == ()
    assert outcome.heartbeat is not None  # real supervision liveness, not fabricated activity


def test_heartbeat_every_gates_the_observable_pulse_but_not_supervision(
    runtime: OrganizationRuntime,
) -> None:
    monitor = OrganizationMonitor(runtime, Supervisor(runtime), heartbeat_every=3)
    outcomes = [monitor.tick() for _ in range(4)]
    # Supervision (reading every agent's health) runs EVERY tick — continuous monitoring.
    assert all(o.supervision is not None for o in outcomes)
    # The observable heartbeat mission fires on tick 1, then every 3rd (bounded journal growth).
    assert [o.heartbeat is not None for o in outcomes] == [True, False, False, True]


def test_the_intent_queue_drains_once() -> None:
    queue = QueueIntentSource(["a", "b"])
    assert list(queue()) == ["a", "b"]
    assert list(queue()) == []  # each submitted mission runs a single time
    queue.submit("c")
    assert list(queue()) == ["c"]


def test_run_forever_loops_until_sleep_stops_it(runtime: OrganizationRuntime) -> None:
    ticks = {"n": 0}

    class _Stop(Exception):
        pass

    def sleep(_seconds: float) -> None:
        ticks["n"] += 1
        if ticks["n"] >= 3:
            raise _Stop

    monitor = OrganizationMonitor(
        runtime, Supervisor(runtime), sleep=sleep, poll_seconds=0.0
    )
    with pytest.raises(_Stop):
        monitor.run_forever()
    assert ticks["n"] == 3  # ticked and slept three times before the injected stop
