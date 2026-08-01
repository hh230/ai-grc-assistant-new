"""AgentMissionRuntime — composes the frozen Core with the agents (ADR 0061/0062/0063).

In-memory composition (no Postgres): the frozen MissionEngine drives a Foreman-planned Plan over the
one Tool execution path — DevToolExecutor resolves each step to a Tool via the Registry, and an
AgentTool resolves the capability to an agent (ADR 0062/0063). No branching executor. With the
InProcessEventBus and the reused MissionAuditSink, this proves the collaboration protocol end to
end: a composite dev mission runs on the Core under tenant:platform. The durable path
(mission-integration.MissionRuntime + Postgres) swaps the store later; the executor stays the same.
"""

from __future__ import annotations

from devteam_agents import (
    Foreman,
    MonitorAgent,
    QaAgent,
    ReviewerAgent,
    SecurityAgent,
    SuiteRunner,
    build_agent_registry,
)
from devteam_contracts import AgentFinding, platform_tenant
from devteam_observability import DevTeamObservability
from devteam_protocol import Agent, AgentCapability
from event_bus import ALL_EVENTS, InProcessEventBus
from mission_engine import MissionEngine
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.mission import Mission
from mission_engine.ports import ExecutionPort
from mission_integration.audit import MissionAuditSink

from devteam_runtime.executor import DevToolExecutor

# Every capability-routed step names its tool, so the executor's default_tool never fires; it points
# at a tool that is always registered (TESTING) purely to satisfy the executor contract.
_DEFAULT_TOOL = AgentCapability.TESTING.value


def _no_findings() -> list[AgentFinding]:
    """The default read-only observation/scan: nothing found. Real log/CI/security sources are
    injected when a monitoring or security mission needs them."""
    return []


def build_default_agents(run_suites: SuiteRunner) -> dict[AgentCapability, Agent]:
    """The read-only spine: TESTING -> QA, MONITORING -> Monitor, SECURITY -> Security,
    REVIEW -> Reviewer. Developer (IMPLEMENTATION) joins with the gated fix-it mission — no Core,
    executor, or registry change, only another entry in this map (§17)."""
    return {
        AgentCapability.TESTING: QaAgent(run_suites),
        AgentCapability.MONITORING: MonitorAgent(_no_findings),
        AgentCapability.SECURITY: SecurityAgent(_no_findings),
        AgentCapability.REVIEW: ReviewerAgent(),
    }


class AgentMissionRuntime:
    """In-memory composition of the frozen Core with the agents-as-Tools registry. Construct with a
    suite runner (and optionally a Foreman); call run_quality_review to drive the composite mission.
    The audit property exposes the reused mission-event stream."""

    def __init__(
        self,
        run_suites: SuiteRunner,
        *,
        foreman: Foreman | None = None,
        observability: DevTeamObservability | None = None,
    ) -> None:
        self._events = InProcessEventBus()
        self._audit = MissionAuditSink()
        self._events.subscribe(ALL_EVENTS, self._audit.record)
        self._observability = observability
        # Opt-in observability: when a DevTeamObservability is injected, courier-wrap the agents,
        # wrap the executor, and subscribe its mission bridge to the bus. Injecting nothing leaves
        # the runtime byte-for-byte as it was (the daemon passes nothing — it stays unchanged).
        agents = build_default_agents(run_suites)
        executor: ExecutionPort = DevToolExecutor(
            build_agent_registry(
                observability.observe_agents(agents) if observability is not None else agents
            ),
            default_tool=_DEFAULT_TOOL,
        )
        if observability is not None:
            executor = observability.observe_executor(executor)
            observability.subscribe(self._events)
        self._engine = MissionEngine(InMemoryMissionStore(), executor, events=self._events)
        self._foreman = foreman or Foreman()

    @property
    def audit(self) -> MissionAuditSink:
        return self._audit

    @property
    def observability(self) -> DevTeamObservability | None:
        """The injected observability layer (if any) — read its ``view`` for live agent state."""
        return self._observability

    def run_quality_review(self, *, principal_id: str = "devteam-foreman") -> Mission:
        """The Foreman plans the capability-routed mission; the frozen engine drives it on the Core
        under tenant:platform. Returns the driven mission (COMPLETED, or FAILED fail-safe)."""
        tenant = platform_tenant(principal_id)
        plan = self._foreman.plan_quality_review()
        mission = self._engine.create("read-only quality review (testing -> review)", tenant)
        self._engine.plan(mission, plan)
        return self._engine.execute(mission)
