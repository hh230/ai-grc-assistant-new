"""The Supervisor — health assessment, stall detection, escalation, recovery, heartbeat."""

from __future__ import annotations

from devteam_contracts import platform_tenant
from devteam_observability import (
    AgentRuntimeRegistry,
    AgentStarted,
    RuntimeStateView,
    agent_id_for,
)
from devteam_organization import OrganizationRuntime, Supervisor, engine_recovery
from devteam_organization.health import assess_health
from devteam_protocol import AgentRole
from mission_engine.lifecycle import MissionStatus
from mission_engine.plan import Plan, PlanStep


def test_a_fresh_platform_is_healthy(runtime: OrganizationRuntime) -> None:
    health = Supervisor(runtime).check()
    assert health.healthy
    assert not health.stalled_agents


def test_a_completed_mission_leaves_the_platform_healthy(runtime: OrganizationRuntime) -> None:
    runtime.run_mission("Implement encryption and map ISO 27001 controls, with tests")
    # Every agent is back IDLE and every session is sealed — nothing looks stalled.
    assert Supervisor(runtime).check().healthy


def test_assess_health_flags_a_stalled_agent_and_mission() -> None:
    registry = AgentRuntimeRegistry()
    cto = agent_id_for(AgentRole.CTO)
    # An agent that started a step long ago and never completed it (a real stall shape).
    registry.observe(
        AgentStarted(
            mission_id="m1", tenant_id="platform", occurred_at=100.0, agent=cto, step_id="s1"
        )
    )
    report = assess_health(RuntimeStateView(registry), now=100.0 + 5000.0, stall_after_s=900.0)
    assert not report.healthy
    assert cto.key in report.stalled_agents
    assert "m1" in report.stalled_missions


def test_supervisor_escalates_a_stall_over_the_live_view(runtime: OrganizationRuntime) -> None:
    cto = agent_id_for(AgentRole.CTO)
    runtime.observability.registry.observe(
        AgentStarted(
            mission_id="m1", tenant_id="platform", occurred_at=100.0, agent=cto, step_id="s1"
        )
    )
    alerts: list[str] = []
    supervisor = Supervisor(
        runtime, on_alert=alerts.append, clock=lambda: 100.0 + 5000.0, stall_after_s=900.0
    )
    outcome = supervisor.supervise()
    assert not outcome.healthy
    assert cto.key in outcome.escalated_agents
    assert any("stalled agent" in alert for alert in alerts)


def test_supervisor_recovers_a_stalled_non_terminal_mission(runtime: OrganizationRuntime) -> None:
    tenant = platform_tenant("test")
    mission = runtime.engine.create("stuck mission", tenant)
    runtime.engine.plan(
        mission, Plan(steps=(PlanStep(description="x", instruction="y", tool="strategy"),))
    )  # PLANNED but never executed — non-terminal
    # Make it look stalled: an active session on its id that never sealed.
    cto = agent_id_for(AgentRole.CTO)
    runtime.observability.registry.observe(
        AgentStarted(
            mission_id=mission.id,
            tenant_id="platform",
            occurred_at=100.0,
            agent=cto,
            step_id="s1",
        )
    )
    supervisor = Supervisor(
        runtime,
        recover=engine_recovery(runtime),
        clock=lambda: 100.0 + 5000.0,
        stall_after_s=900.0,
    )
    outcome = supervisor.supervise()
    assert mission.id in outcome.recovered_missions
    # The mission was cancelled through the engine's public API (fail-safe), not killed internally.
    recovered = runtime.engine.get(mission.id, tenant)
    assert recovered is not None and recovered.status is MissionStatus.CANCELLED


def test_heartbeat_runs_an_observed_health_mission(runtime: OrganizationRuntime) -> None:
    mission = Supervisor(runtime).heartbeat()
    assert mission.status is MissionStatus.COMPLETED
    supervisor_state = runtime.view.agent(agent_id_for(AgentRole.SUPERVISOR))
    assert supervisor_state is not None
    completed = supervisor_state["completed_missions"]
    assert isinstance(completed, int) and completed >= 1
