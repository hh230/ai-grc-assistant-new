"""CTO, QA, GRC Expert, DevTeam, CEO, and Supervisor jobs — orchestration over connectors (§11).

Each obtains evidence EXCLUSIVELY from a connector (via the registry): the CTO from GitHub, QA from
Test Reports, the GRC Expert from Compliance, and the CEO / DevTeam / Supervisor from the Runtime
connector. No direct integrations. Missions open only on real evidence; an unavailable connector is
recorded and opens nothing.
"""

from __future__ import annotations

from collections.abc import Mapping

from devteam_protocol import AgentCapability, AgentRole

from devteam_organization.connectors import ConnectorRegistry
from devteam_organization.jobs import evidence
from devteam_organization.jobs.framework import (
    JobContext,
    JobHealth,
    JobResult,
    MissionGate,
    Observation,
    Schedule,
)

_ENGINEERING_STAGES = (
    AgentCapability.STRATEGY,
    AgentCapability.ARCHITECTURE,
    AgentCapability.TESTING,
    AgentCapability.DELIVERY,
)
_QA_STAGES = (AgentCapability.STRATEGY, AgentCapability.TESTING, AgentCapability.DELIVERY)
_GRC_STAGES = (AgentCapability.STRATEGY, AgentCapability.GRC, AgentCapability.DELIVERY)
_EXEC_STAGES = (AgentCapability.STRATEGY, AgentCapability.DELIVERY)


class CTOJob:
    id = "cto.engineering_review"
    name = "Engineering Review"
    owner = AgentRole.CTO
    connector_id = "github"

    def __init__(self, registry: ConnectorRegistry, *, schedule: Schedule) -> None:
        self._registry = registry
        self.schedule = schedule
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"github connector {result.status.value}")
        observations: list[Observation] = []
        problems: list[str] = []
        failure = result.data.get("latest_failure")
        if isinstance(failure, Mapping):
            branch = evidence.field_str(failure, "head_branch")
            problems.append(f"build:{branch}")
            summary = evidence.field_str(failure, "summary")
            observations.append(Observation(f"failed build: {summary}", "high"))
        prs = evidence.rows(result, "open_prs")
        if prs:
            numbers = ",".join(str(evidence.field_int(pr, "number", 0)) for pr in prs)
            problems.append(f"prs:{numbers}")
            observations.append(Observation(f"{len(prs)} open PR(s) pending review", "medium"))
        return self._gate.evaluate(
            signature=";".join(problems),
            goal=f"CTO: engineering work pending — {', '.join(problems)}. Plan and deliver.",
            degraded_summary=f"{len(problems)} engineering item(s) pending",
            healthy_summary="no failed builds, no pending pull requests",
            stages=_ENGINEERING_STAGES,
            observations=tuple(observations),
        )


class QAJob:
    id = "qa.regression_review"
    name = "Regression Review"
    owner = AgentRole.QA
    connector_id = "test_reports"

    def __init__(self, registry: ConnectorRegistry, *, schedule: Schedule) -> None:
        self._registry = registry
        self.schedule = schedule
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"test-reports connector {result.status.value}")
        failing = evidence.str_list(result, "failing")
        return self._gate.evaluate(
            signature=",".join(sorted(failing)),
            goal=f"QA: {len(failing)} failing/flaky test(s): {', '.join(failing[:3])}.",
            degraded_summary=f"{len(failing)} failing/flaky test(s)",
            healthy_summary="no failing or flaky tests reported",
            stages=_QA_STAGES,
            observations=tuple(Observation(name, "high") for name in failing[:5]),
        )


class GRCExpertJob:
    id = "grc.compliance_review"
    name = "Compliance Review"
    owner = AgentRole.GRC_EXPERT
    connector_id = "compliance"

    def __init__(self, registry: ConnectorRegistry, *, schedule: Schedule) -> None:
        self._registry = registry
        self.schedule = schedule
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"compliance connector {result.status.value}")
        gaps = evidence.str_list(result, "gaps")
        return self._gate.evaluate(
            signature=",".join(sorted(gaps)),
            goal=f"GRC: {len(gaps)} control gap(s)/stale evidence: {', '.join(gaps[:3])}.",
            degraded_summary=f"{len(gaps)} compliance gap(s)",
            healthy_summary="controls covered; evidence fresh",
            stages=_GRC_STAGES,
            observations=tuple(Observation(gap, "medium") for gap in gaps[:5]),
        )


class DevTeamJob:
    id = "devteam.delivery_review"
    name = "Delivery Review"
    owner = AgentRole.DEVTEAM
    connector_id = "runtime"

    def __init__(self, registry: ConnectorRegistry, *, schedule: Schedule) -> None:
        self._registry = registry
        self.schedule = schedule

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"runtime connector {result.status.value}")
        awaiting = evidence.str_list(result, "awaiting_missions")
        if awaiting:
            # Delivery is human-gated (ADR 0044): surface pending work, never self-approve.
            return JobResult(
                JobHealth.DEGRADED,
                f"{len(awaiting)} mission(s) awaiting delivery approval (human gate)",
                tuple(Observation(f"awaiting approval: {mid}", "medium") for mid in awaiting),
            )
        return JobResult.healthy("no missions awaiting delivery")


class CEOJob:
    id = "ceo.kpi_review"
    name = "KPI Review"
    owner = AgentRole.CEO
    connector_id = "runtime"

    def __init__(
        self,
        registry: ConnectorRegistry,
        *,
        schedule: Schedule,
        open_missions_threshold: int,
        incident_threshold: int,
    ) -> None:
        self._registry = registry
        self.schedule = schedule
        self._open_threshold = open_missions_threshold
        self._incident_threshold = incident_threshold
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"runtime connector {result.status.value}")
        open_missions = evidence.count(result, "open_missions")
        incidents = evidence.count(result, "incidents")
        breaches: list[str] = []
        if open_missions > self._open_threshold:
            breaches.append(f"open-missions:{open_missions}>{self._open_threshold}")
        if incidents >= self._incident_threshold and self._incident_threshold > 0:
            breaches.append(f"incidents:{incidents}")
        return self._gate.evaluate(
            signature=";".join(breaches),
            goal=f"CEO: KPI thresholds exceeded — {', '.join(breaches)}. Escalate + prioritize.",
            degraded_summary=f"{len(breaches)} KPI threshold breach(es)",
            healthy_summary=f"KPIs OK ({open_missions} open, {incidents} incidents)",
            stages=_EXEC_STAGES,
            observations=tuple(Observation(b, "high") for b in breaches),
            escalate=True,
        )


class SupervisorJob:
    id = "supervisor.supervise"
    name = "Supervisor"
    owner = AgentRole.SUPERVISOR
    connector_id = "runtime"

    def __init__(self, registry: ConnectorRegistry, *, schedule: Schedule) -> None:
        self._registry = registry
        self.schedule = schedule
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"runtime connector {result.status.value}")
        observations: list[Observation] = []
        problems: list[str] = []
        for label in evidence.str_list(result, "workers_down"):
            problems.append(f"worker:{label}")
            observations.append(Observation(f"worker down: {label}", "critical"))
        for key in evidence.str_list(result, "stalled_agents"):
            problems.append(f"agent:{key}")
            observations.append(Observation(f"stalled agent: {key}", "high"))
        for mid in evidence.str_list(result, "stalled_missions"):
            problems.append(f"mission:{mid}")
        return self._gate.evaluate(
            signature=",".join(sorted(problems)),
            goal=f"Supervisor: platform unhealthy — {', '.join(problems)}. Recover.",
            degraded_summary=f"{len(problems)} health problem(s)",
            healthy_summary="all agents and workers healthy",
            stages=_EXEC_STAGES,
            observations=tuple(observations),
            escalate=True,
        )
