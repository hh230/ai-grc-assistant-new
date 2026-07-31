"""CISO recurring jobs — orchestration over connectors (§11).

Six jobs the CISO owns. Each obtains evidence EXCLUSIVELY from a connector (via the registry) — no
direct probing — and, through a ``MissionGate``, opens a Mission once per problem episode on real
evidence. An unavailable connector ⇒ the job records "unavailable" and opens no mission.
"""

from __future__ import annotations

from devteam_protocol import AgentCapability, AgentRole

from devteam_organization.connectors import ConnectorRegistry
from devteam_organization.jobs import evidence
from devteam_organization.jobs.framework import (
    JobContext,
    JobResult,
    MissionGate,
    Observation,
    Schedule,
)

# CISO missions are governed CEO → CISO → DevTeam responses (scoped, not the whole pipeline).
_CISO_STAGES = (AgentCapability.STRATEGY, AgentCapability.SECURITY_REVIEW, AgentCapability.DELIVERY)


class WebsiteHealthJob:
    id = "ciso.website_health"
    name = "Website Health Monitor"
    owner = AgentRole.CISO
    connector_id = "website"

    def __init__(
        self, registry: ConnectorRegistry, *, schedule: Schedule, failure_threshold: int
    ) -> None:
        self._registry = registry
        self.schedule = schedule
        self._threshold = failure_threshold
        self._failures: dict[str, int] = {}
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"website connector {result.status.value}")
        observations: list[Observation] = []
        failing: list[str] = []
        for row in evidence.rows(result, "endpoints"):
            url = evidence.field_str(row, "url")
            name = evidence.field_str(row, "name", url)
            if not evidence.field_bool(row, "ok"):
                self._failures[url] = self._failures.get(url, 0) + 1
                observations.append(Observation(f"{name} down", "high"))
                if self._failures[url] >= self._threshold:
                    failing.append(name)
            else:
                self._failures[url] = 0
                if evidence.field_bool(row, "slow"):
                    observations.append(Observation(f"{name} slow", "medium"))
        return self._gate.evaluate(
            signature=",".join(sorted(failing)),
            goal=f"CISO: application endpoint(s) unhealthy — {', '.join(failing)}. Investigate.",
            degraded_summary=f"{len(failing)} endpoint(s) repeatedly failing",
            healthy_summary=f"{len(evidence.rows(result, 'endpoints'))} endpoint(s) responding",
            stages=_CISO_STAGES,
            observations=tuple(observations),
        )


class SecurityHeadersJob:
    id = "ciso.security_headers"
    name = "Security Headers Monitor"
    owner = AgentRole.CISO
    connector_id = "http_security"

    def __init__(self, registry: ConnectorRegistry, *, schedule: Schedule) -> None:
        self._registry = registry
        self.schedule = schedule
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"http-security connector {result.status.value}")
        observations: list[Observation] = []
        degraded: list[str] = []
        for row in evidence.rows(result, "endpoints"):
            if not evidence.field_bool(row, "reachable"):
                continue
            missing = _string_list(row.get("missing"))
            if missing:
                name = evidence.field_str(row, "name", evidence.field_str(row, "url"))
                degraded.append(f"{name}:{'+'.join(missing)}")
                observations.append(Observation(f"{name} missing {missing}", "medium"))
        return self._gate.evaluate(
            signature=",".join(sorted(degraded)),
            goal=f"CISO: security headers degraded — {'; '.join(degraded)}. Restore configuration.",
            degraded_summary=f"{len(degraded)} endpoint(s) with missing headers",
            healthy_summary="all configured endpoints send required headers",
            stages=_CISO_STAGES,
            observations=tuple(observations),
        )


class TlsCertificateJob:
    id = "ciso.tls_certificate"
    name = "TLS Certificate Monitor"
    owner = AgentRole.CISO
    connector_id = "tls"

    def __init__(
        self, registry: ConnectorRegistry, *, schedule: Schedule, warn_days: int
    ) -> None:
        self._registry = registry
        self.schedule = schedule
        self._warn_days = warn_days
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"tls connector {result.status.value}")
        observations: list[Observation] = []
        problems: list[str] = []
        for row in evidence.rows(result, "hosts"):
            host = evidence.field_str(row, "host")
            days = evidence.field_int(row, "days_to_expiry")
            if not evidence.field_bool(row, "hostname_valid"):
                problems.append(f"{host}:hostname")
                observations.append(Observation(f"{host}: hostname invalid", "high"))
            elif days is not None and days <= self._warn_days:
                problems.append(f"{host}:expiry")
                observations.append(Observation(f"{host}: expires in {days} days", "high"))
        return self._gate.evaluate(
            signature=",".join(sorted(problems)),
            goal=f"CISO: TLS certificate action needed — {', '.join(problems)}. Renew/fix.",
            degraded_summary=f"{len(problems)} certificate issue(s)",
            healthy_summary=f"{len(evidence.rows(result, 'hosts'))} certificate(s) valid",
            stages=_CISO_STAGES,
            observations=tuple(observations),
        )


class DependencySecurityJob:
    id = "ciso.dependency_security"
    name = "Dependency Security Monitor"
    owner = AgentRole.CISO
    connector_id = "vulnerability"

    def __init__(self, registry: ConnectorRegistry, *, schedule: Schedule) -> None:
        self._registry = registry
        self.schedule = schedule
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"vulnerability connector {result.status.value}")
        high = evidence.rows(result, "high")
        listed = ", ".join(evidence.field_str(v, "package") for v in high[:5])
        signature = ",".join(
            sorted(
                f"{evidence.field_str(v, 'package')}:{evidence.field_str(v, 'severity')}"
                for v in high
            )
        )
        return self._gate.evaluate(
            signature=signature,
            goal=f"CISO: {len(high)} high/critical dependency vuln(s) — {listed}. Remediate.",
            degraded_summary=f"{len(high)} high/critical vulnerabilities",
            healthy_summary="no high/critical dependency vulnerabilities",
            stages=_CISO_STAGES,
            observations=tuple(
                Observation(evidence.field_str(v, "package"), evidence.field_str(v, "severity"))
                for v in high
            ),
        )


class SecretExposureJob:
    id = "ciso.secret_exposure"
    name = "Secret Exposure Monitor"
    owner = AgentRole.CISO
    connector_id = "secrets"

    def __init__(self, registry: ConnectorRegistry, *, schedule: Schedule) -> None:
        self._registry = registry
        self.schedule = schedule
        self._gate = MissionGate()

    def inspect(self, context: JobContext) -> JobResult:
        result = self._registry.fetch(self.connector_id)
        if not result.available:
            return JobResult.unavailable(f"secrets connector {result.status.value}")
        findings = evidence.str_list(result, "findings")
        return self._gate.evaluate(
            signature=",".join(sorted(findings)),
            goal=f"CISO: {len(findings)} secret exposure finding(s) detected. Rotate + remove.",
            degraded_summary=f"{len(findings)} secret finding(s)",
            healthy_summary="no secret exposures found",
            stages=_CISO_STAGES,
            observations=tuple(Observation(f, "critical") for f in findings[:5]),
        )


class RuntimeHealthJob:
    id = "ciso.runtime_health"
    name = "Runtime Health Monitor"
    owner = AgentRole.CISO
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
            goal=f"CISO: runtime unhealthy — {', '.join(problems)}. Restore services.",
            degraded_summary=f"{len(problems)} runtime problem(s)",
            healthy_summary="runtime healthy; all workers running",
            stages=_CISO_STAGES,
            observations=tuple(observations),
            escalate=True,
        )


def _string_list(value: object) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []
