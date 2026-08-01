"""DevIntakeRuntime — the full trigger -> intake -> agent-mission pipeline, in-memory.

Composition only, no new abstractions (ADR 0061-0064): a TriggerSource-fed IntakeGateway correlates
each trigger, creates a Foreman-planned, capability-routed agent Mission (testing -> review) on the
Mission Engine via an in-memory MissionDriver, records to the reused MissionAuditSink, and frees the
correlation ref when the mission ends. The durable path swaps the in-memory driver + store later.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from assistant_runtime.capability import Capability
from assistant_runtime.capability_catalog import CapabilityCatalog
from assistant_runtime.mission_catalog import MissionCatalog, MissionType
from assistant_runtime.selector import CapabilitySelector
from devteam_agents import Foreman, SuiteRunner, build_agent_registry
from devteam_intake import (
    CorrelationDeactivator,
    CorrelationRepository,
    IntakeGateway,
    IntakeOutcome,
    MissionIntake,
    StoreMissionCorrelator,
    TriggerSource,
)
from devteam_protocol import AgentCapability
from event_bus import ALL_EVENTS, InProcessEventBus
from mission_engine import MissionEngine, Plan
from mission_engine.adapters import InMemoryMissionStore
from mission_integration.audit import MissionAuditSink
from pipeline_contracts import TenantContext

from devteam_runtime.agent_runtime import build_default_agents
from devteam_runtime.executor import DevToolExecutor

T = TypeVar("T")

# The dev capability a trigger asks for, and the mission type it resolves to.
_QUALITY_REVIEW = "quality_review"
_QUALITY_REVIEW_MISSION = "quality_review_mission"


class _InMemoryMissionDriver:
    """A MissionDriver over one in-memory engine (run_transition applies to it) — the dev team's
    in-memory realization of assistant-runtime's MissionDriver port."""

    def __init__(self, engine: MissionEngine) -> None:
        self._engine = engine

    def run_transition(self, apply: Callable[[MissionEngine], T]) -> T:
        return apply(self._engine)


def _quality_review_mission(foreman: Foreman) -> MissionType:
    """The dev mission type behind the quality_review capability: its plan factory IS the Foreman's
    capability-routed plan (ADR 0063), translated to the Core's (goal, Plan)."""

    def factory(_inputs: Mapping[str, Any], _tenant: TenantContext) -> tuple[str, Plan]:
        return "read-only quality review (testing -> review)", foreman.plan_quality_review()

    return MissionType(id=_QUALITY_REVIEW_MISSION, plan_factory=factory)


class DevIntakeRuntime:
    """The composed intake pipeline. submit(raw, source) runs a trigger to a governed agent Mission
    (create) or an audited signal (update). audit and repository expose the reused terminals."""

    def __init__(self, run_suites: SuiteRunner, *, foreman: Foreman | None = None) -> None:
        the_foreman = foreman or Foreman()
        registry = build_agent_registry(build_default_agents(run_suites))
        self._events = InProcessEventBus()
        self._audit = MissionAuditSink()
        self._events.subscribe(ALL_EVENTS, self._audit.record)
        self._repository = CorrelationRepository()
        self._events.subscribe(ALL_EVENTS, CorrelationDeactivator(self._repository).handle)
        engine = MissionEngine(
            InMemoryMissionStore(),
            DevToolExecutor(registry, default_tool=AgentCapability.TESTING.value),
            events=self._events,
        )
        capabilities = CapabilityCatalog(
            [Capability(id=_QUALITY_REVIEW, resolver=_QUALITY_REVIEW_MISSION)]
        )
        missions = MissionCatalog([_quality_review_mission(the_foreman)])
        intake = MissionIntake(
            selector=CapabilitySelector(capabilities, fallback_id=_QUALITY_REVIEW),
            mission_catalog=missions,
            driver=_InMemoryMissionDriver(engine),
            repository=self._repository,
            events=self._events,
        )
        self._gateway = IntakeGateway(
            correlator=StoreMissionCorrelator(self._repository), intake=intake
        )

    @property
    def audit(self) -> MissionAuditSink:
        return self._audit

    @property
    def repository(self) -> CorrelationRepository:
        return self._repository

    def submit(self, raw: Mapping[str, object], source: TriggerSource) -> IntakeOutcome:
        return self._gateway.submit(raw, source)
