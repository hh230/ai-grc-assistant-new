"""Intake boundary E2E: trigger -> correlate -> create/update, reusing assistant-runtime + the Core.

The mission's internal plan here is a trivial single read-only step run by the EchoExecutor — this
test exercises the *intake + correlation* boundary, not the agents (a Foreman-planned, agent-routed
mission is wired in devteam-runtime). Proves: a new entity creates & registers a mission; a repeat
for the same entity updates it (no duplicate); distinct entities create distinct missions.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from assistant_runtime.capability import Capability
from assistant_runtime.capability_catalog import CapabilityCatalog
from assistant_runtime.mission_catalog import MissionCatalog, MissionType
from assistant_runtime.selector import CapabilitySelector
from devteam_contracts import platform_tenant
from devteam_intake import (
    CIFailureSource,
    CorrelationRepository,
    IntakeGateway,
    ManualRequestSource,
    MissionIntake,
    StoreMissionCorrelator,
)
from event_bus.bus import RecordingEventBus
from mission_engine import EchoExecutor, MissionEngine, Plan
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.plan import single_step_plan
from pipeline_contracts import TenantContext

T = TypeVar("T")


def _quality_review_plan(_inputs: Mapping[str, Any], _tenant: TenantContext) -> tuple[str, Plan]:
    return "read-only quality review", single_step_plan("run the quality gate")


class _FakeDriver:
    """A MissionDriver over an in-memory engine: run_transition applies to the engine directly."""

    def __init__(self, engine: MissionEngine) -> None:
        self._engine = engine

    def run_transition(self, apply: Callable[[MissionEngine], T]) -> T:
        return apply(self._engine)


def _build() -> tuple[IntakeGateway, CorrelationRepository, RecordingEventBus]:
    capabilities = CapabilityCatalog([Capability(id="quality_review", resolver="qr")])
    missions = MissionCatalog([MissionType(id="qr", plan_factory=_quality_review_plan)])
    selector = CapabilitySelector(capabilities, fallback_id="quality_review")
    repository = CorrelationRepository()
    events = RecordingEventBus()
    driver = _FakeDriver(MissionEngine(InMemoryMissionStore(), EchoExecutor()))
    intake = MissionIntake(
        selector=selector,
        mission_catalog=missions,
        driver=driver,
        repository=repository,
        events=events,
    )
    gateway = IntakeGateway(correlator=StoreMissionCorrelator(repository), intake=intake)
    return gateway, repository, events


def test_a_new_trigger_creates_and_registers_a_mission() -> None:
    gateway, repository, _ = _build()
    outcome = gateway.submit({"pipeline": "api", "detail": "failed"}, CIFailureSource())
    assert outcome.action == "created"
    assert repository.find_active(platform_tenant(), "ci:pipeline:api") == outcome.mission_id


def test_a_repeat_trigger_for_the_same_entity_updates_not_duplicates() -> None:
    gateway, _, events = _build()
    first = gateway.submit({"pipeline": "api"}, CIFailureSource())
    second = gateway.submit({"pipeline": "api"}, CIFailureSource())  # same ref, still active
    assert first.action == "created"
    assert second.action == "updated"
    assert second.mission_id == first.mission_id  # no duplicate mission
    assert any(event.name == "mission.signal_received" for event in events.events)


def test_distinct_entities_create_distinct_missions() -> None:
    gateway, _, _ = _build()
    api = gateway.submit({"pipeline": "api"}, CIFailureSource())
    web = gateway.submit({"pipeline": "web"}, CIFailureSource())
    assert api.action == "created" and web.action == "created"
    assert api.mission_id != web.mission_id


def test_a_manual_request_also_creates() -> None:
    gateway, _, _ = _build()
    outcome = gateway.submit({"request": "investigate flaky suite"}, ManualRequestSource())
    assert outcome.action == "created"
