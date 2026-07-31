"""``OrganizationRuntime`` — the AI Organization composed over the FROZEN v2 Core (§11).

A composition, not a runtime: the frozen ``MissionEngine`` drives a CEO-planned, capability-routed
Plan over the ONE Tool execution path — ``DevToolExecutor`` (reused from the engineering squad's
runtime) resolves each step to an ``AgentTool`` that resolves the capability to an org agent.
Every step is observed through the existing ``ObservingExecutor`` into the journal the Dashboard
reads, so the organization appears in the existing Mission Timeline, Agent Inspector, and Executive
views with no new engine, registry, bus, dashboard, or state model.

Observability is always on here (the organization is inherently observable — that is the point); a
composition root passes a journaling ``DevTeamObservability`` so a separate Dashboard sees it.
The organization's QA member is the squad's ``QaAgent``, reused — never duplicated.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from devteam_agents import QaAgent, SuiteRunner, build_agent_registry
from devteam_contracts import platform_tenant
from devteam_observability import DevTeamObservability, RuntimeStateView
from devteam_protocol import Agent, AgentCapability
from devteam_runtime import DevToolExecutor
from event_bus import ALL_EVENTS, InProcessEventBus
from mission_engine import MissionEngine
from mission_engine.adapters import InMemoryMissionStore
from mission_engine.mission import Mission
from mission_engine.plan import Plan, PlanStep
from mission_engine.ports import ExecutionPort
from mission_integration.audit import MissionAuditSink

from devteam_organization.agents import (
    CEOAgent,
    CISOAgent,
    CTOAgent,
    DevTeamAgent,
    GRCExpertAgent,
    HealthSource,
    SupervisorAgent,
    ThreatReview,
)
from devteam_organization.health import HealthReport, assess_health
from devteam_organization.knowledge import FrameworkKnowledge
from devteam_organization.planner import OrganizationPlanner

# Every step names its capability tool, so the executor's default never fires; it points at a tool
# that is always registered (STRATEGY) to satisfy the executor contract.
_DEFAULT_TOOL = AgentCapability.STRATEGY.value
# A step (or an agent) executing longer than this is flagged stalled by the Supervisor. Generous:
# the deterministic agents finish in milliseconds; a real stall means something is genuinely wrong.
_DEFAULT_STALL_AFTER_S = 900.0


def build_organization_agents(
    run_suites: SuiteRunner,
    *,
    health: HealthSource,
    threat_review: ThreatReview | None = None,
    knowledge: FrameworkKnowledge | None = None,
) -> dict[AgentCapability, Agent]:
    """The organization's capability -> agent map. TESTING is the engineering squad's ``QaAgent``,
    reused as the organization's quality member. SUPERVISION is the Supervisor's health check. New
    seams (threat review, framework knowledge) are injected; the defaults are deterministic."""
    ciso = CISOAgent(threat_review) if threat_review is not None else CISOAgent()
    grc = GRCExpertAgent(knowledge) if knowledge is not None else GRCExpertAgent()
    return {
        AgentCapability.STRATEGY: CEOAgent(),
        AgentCapability.ARCHITECTURE: CTOAgent(),
        AgentCapability.SECURITY_REVIEW: ciso,
        AgentCapability.GRC: grc,
        AgentCapability.TESTING: QaAgent(run_suites),
        AgentCapability.DELIVERY: DevTeamAgent(),
        AgentCapability.SUPERVISION: SupervisorAgent(health),
    }


class OrganizationRuntime:
    """In-memory composition of the frozen Core with the AI Organization, always observed. Construct
    with a suite runner (the QA member's real gate); call ``run_mission`` to drive a governed
    organization mission, or ``run_health_check`` for a Supervisor heartbeat mission."""

    def __init__(
        self,
        run_suites: SuiteRunner,
        *,
        observability: DevTeamObservability | None = None,
        planner: OrganizationPlanner | None = None,
        threat_review: ThreatReview | None = None,
        knowledge: FrameworkKnowledge | None = None,
        stall_after_s: float = _DEFAULT_STALL_AFTER_S,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._events = InProcessEventBus()
        self._audit = MissionAuditSink()
        self._events.subscribe(ALL_EVENTS, self._audit.record)
        # Always-on observability: the organization is built to be watched. A composition root can
        # pass one that also journals to the Dashboard's file; the default is in-memory only.
        self._obs = observability or DevTeamObservability()
        self._clock = clock
        self._stall_after_s = stall_after_s
        agents = build_organization_agents(
            run_suites,
            health=self._health_report,
            threat_review=threat_review,
            knowledge=knowledge,
        )
        executor: ExecutionPort = DevToolExecutor(
            build_agent_registry(self._obs.observe_agents(agents)), default_tool=_DEFAULT_TOOL
        )
        executor = self._obs.observe_executor(executor)
        self._obs.subscribe(self._events)
        self._engine = MissionEngine(InMemoryMissionStore(), executor, events=self._events)
        self._planner = planner or OrganizationPlanner()

    def _health_report(self) -> HealthReport:
        """The Supervisor agent's live health source: assess the runtime's own view, now."""
        return assess_health(
            self._obs.view, now=self._clock(), stall_after_s=self._stall_after_s
        )

    @property
    def view(self) -> RuntimeStateView:
        """The read API the Dashboard consumes — the organization's live agent + mission state."""
        return self._obs.view

    @property
    def audit(self) -> MissionAuditSink:
        return self._audit

    @property
    def observability(self) -> DevTeamObservability:
        return self._obs

    @property
    def engine(self) -> MissionEngine:
        return self._engine

    @property
    def planner(self) -> OrganizationPlanner:
        return self._planner

    def run_mission(
        self,
        goal: str,
        *,
        stages: list[AgentCapability] | None = None,
        principal_id: str = "org-ceo",
    ) -> Mission:
        """Open, plan (CEO delegation), and drive a governed organization mission under
        tenant:platform. The CEO leads, the DevTeam closes, and the relevant middle stages run in
        between — all observed. Returns the driven mission (COMPLETED, or FAILED fail-safe)."""
        tenant = platform_tenant(principal_id)
        plan = self._planner.plan(goal, stages=stages)
        mission = self._engine.create(goal, tenant)
        self._engine.plan(mission, plan)
        return self._engine.execute(mission)

    def run_health_check(self, *, principal_id: str = "org-supervisor") -> Mission:
        """Run the Supervisor's heartbeat as a real, observed mission: one SUPERVISION step that
        assesses live platform health and records a healthy/escalate decision. This is what makes
        the Supervisor a live participant in the Dashboard, doing real work — not a thread."""
        tenant = platform_tenant(principal_id)
        plan = Plan(
            steps=(
                PlanStep(
                    description="Supervisor: platform health check",
                    instruction="assess platform health",
                    tool=AgentCapability.SUPERVISION.value,
                ),
            )
        )
        mission = self._engine.create("platform health check", tenant)
        self._engine.plan(mission, plan)
        return self._engine.execute(mission)
