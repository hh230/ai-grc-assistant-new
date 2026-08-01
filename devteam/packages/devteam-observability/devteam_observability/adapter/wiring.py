"""``DevTeamObservability`` — one-call wiring of the layer into a DevTeam runtime.

Composition only: it builds the registry (seeded with the whole platform roster), the read view, the
shared decision capture, and the mission bridge, and hands back the two wrappers a composition root
applies opt-in:

    obs = DevTeamObservability()
    agents = obs.observe_agents(build_default_agents(runner))   # courier-wrap the agents
    registry = build_agent_registry(agents)
    executor = obs.observe_executor(DevToolExecutor(registry, default_tool=...))
    engine = MissionEngine(store, executor, events=bus)
    obs.subscribe(bus)
    ...run missions...
    obs.view.snapshot()          # exactly what a dashboard route would return

Everything is additive: the agents, the engine, the Tool Registry, and the Monitor are untouched. A
runtime that never calls ``DevTeamObservability`` behaves precisely as before. Pass ``downstreams``
(e.g. a journal, the "journal last" increment) to fan every runtime event out to further observers
across the process boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from devteam_protocol import Agent, AgentCapability
from event_bus.bus import EventBus
from mission_engine.ports import ExecutionPort

from devteam_observability.adapter.capture import StepCapture
from devteam_observability.adapter.mission_bridge import MissionEventBridge
from devteam_observability.adapter.observing_executor import ObservingExecutor
from devteam_observability.adapter.result_courier import ResultCourier
from devteam_observability.adapter.roster import seed_roster
from devteam_observability.core import (
    AgentRuntimeRegistry,
    CompositeObserver,
    RuntimeObserver,
    RuntimeStateView,
    build_view_from_journal,
)


class DevTeamObservability:
    """The DevTeam observability composition. Build one per runtime; read state via ``view``."""

    def __init__(self, *, downstreams: Sequence[RuntimeObserver] = ()) -> None:
        # ``downstreams`` are INGRESS observers (e.g. a JournalingObserver): they receive every
        # runtime FACT, alongside the registry. Derived ``AgentStatusChanged`` events stay internal
        # to the registry's feed — a journal records facts only, and a replay re-derives the rest.
        extra = list(downstreams)
        self._registry = AgentRuntimeRegistry()
        seed_roster(self._registry)
        self._capture = StepCapture()
        self._observer: RuntimeObserver = CompositeObserver([self._registry, *extra])
        self._bridge = MissionEventBridge(self._observer)

    @property
    def registry(self) -> AgentRuntimeRegistry:
        return self._registry

    @property
    def view(self) -> RuntimeStateView:
        """The read API a dashboard consumes. A fresh façade each call; the state lives in the
        registry."""
        return RuntimeStateView(self._registry)

    def observe_agents(
        self, agents: Mapping[AgentCapability, Agent]
    ) -> dict[AgentCapability, Agent]:
        """Courier-wrap each agent so its result reaches the executor. Same map shape in and out,
        so it drops straight into ``build_agent_registry``."""
        return {cap: ResultCourier(agent, self._capture) for cap, agent in agents.items()}

    def observe_executor(self, inner: ExecutionPort) -> ObservingExecutor:
        """Wrap the ``DevToolExecutor`` so each agent step emits runtime events."""
        return ObservingExecutor(inner, self._observer, self._capture)

    def subscribe(self, bus: EventBus) -> None:
        """Wire the mission bridge to the runtime's Event Bus (the one the engine publishes to)."""
        self._bridge.subscribe(bus)


def devteam_view_from_journal(path: Path | str) -> RuntimeStateView:
    """Reader side for the DevTeam dashboard (a separate process): a ``RuntimeStateView`` rebuilt
    from the journal and seeded with the whole platform roster the SAME way the live runtime seeds
    it (``seed_roster``, display names and all), so the reconstruction is byte-identical to the live
    view. The Dashboard reads THIS view — never the file — so the storage stays replaceable."""
    return build_view_from_journal(path, seed=seed_roster)
