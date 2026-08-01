"""Stateless problem emission — jobs observe and emit, they never own (ADR 0065, S4b-2b-2 rules).

Detection ≠ ownership (rule 1): a job's whole job is ``observe → emit ProblemSignal``; the moment a
signal exists the Lifecycle owns the problem — the job keeps no memory of whether it is open, how
many attempts ran, or whether it closed (rule 2, stateless). That state lives in the ProblemLedger,
the LifecycleCoordinator, and the AttemptStore, so a job can restart with zero lost context.

These are pure emitters: connector evidence in → ProblemSignals out, one per affected asset. One
emitter per domain; a new domain is a new emitter, no core change. The lifecycle's correlation
dedups repeats and its verification absorbs transient blips, so emitters need no smoothing state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Protocol, runtime_checkable

from devteam_organization.lifecycle.correlation import ProblemSignal, Severity
from devteam_organization.lifecycle.strategies import MissionType


def _rows(data: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = data.get(key)
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _str(row: Mapping[str, object], key: str, default: str = "") -> str:
    value = row.get(key)
    return value if isinstance(value, str) else default


def _truthy(row: Mapping[str, object], key: str) -> bool:
    return row.get(key) is True


def _str_list(data: Mapping[str, object], key: str) -> list[str]:
    value = data.get(key)
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _signal(mission_type: str, asset: str, evidence: str, severity: Severity) -> ProblemSignal:
    return ProblemSignal(
        mission_type=mission_type,
        asset=asset,
        evidence_signature=evidence,
        goal=f"resolve {evidence} on {asset}",
        summary=f"{mission_type}: {evidence} on {asset}",
        severity=severity,
    )


@runtime_checkable
class ProblemEmitter(Protocol):
    """Maps one connector's evidence to zero or more ProblemSignals. Stateless — the same evidence
    always yields the same signals; the lifecycle owns everything after emission."""

    @property
    def connector_id(self) -> str: ...

    def emit(self, data: Mapping[str, object]) -> list[ProblemSignal]: ...


class WebsiteEmitter:
    connector_id = "website"

    def emit(self, data: Mapping[str, object]) -> list[ProblemSignal]:
        signals: list[ProblemSignal] = []
        for row in _rows(data, "endpoints"):
            url = _str(row, "url")
            if not url:
                continue
            if not _truthy(row, "ok"):
                signals.append(_signal(MissionType.OPERATIONS, url, "endpoint_down", Severity.HIGH))
            elif _truthy(row, "slow"):
                signals.append(
                    _signal(MissionType.OPERATIONS, url, "endpoint_slow", Severity.MEDIUM)
                )
        return signals


class TlsEmitter:
    connector_id = "tls"

    def emit(self, data: Mapping[str, object]) -> list[ProblemSignal]:
        signals: list[ProblemSignal] = []
        for row in _rows(data, "hosts"):
            host = _str(row, "host")
            if not host:
                continue
            if not _truthy(row, "hostname_valid"):
                signals.append(_signal(MissionType.SECURITY, host, "tls_hostname", Severity.HIGH))
            elif _truthy(row, "expiring"):
                signals.append(_signal(MissionType.SECURITY, host, "tls_expiry", Severity.HIGH))
        return signals


class HttpSecurityEmitter:
    connector_id = "http_security"

    def emit(self, data: Mapping[str, object]) -> list[ProblemSignal]:
        signals: list[ProblemSignal] = []
        for row in _rows(data, "endpoints"):
            url = _str(row, "url")
            missing = _str_list(row, "missing")
            if url and missing:
                evidence = "missing_header:" + "+".join(sorted(missing))
                signals.append(_signal(MissionType.SECURITY, url, evidence, Severity.MEDIUM))
        return signals


class VulnerabilityEmitter:
    connector_id = "vulnerability"

    def emit(self, data: Mapping[str, object]) -> list[ProblemSignal]:
        signals: list[ProblemSignal] = []
        for row in _rows(data, "high"):
            package = _str(row, "package")
            if not package:
                continue
            level = _str(row, "severity", "high")
            evidence = f"cve:{level}"
            signals.append(_signal(MissionType.SECURITY, package, evidence, _severity(level)))
        return signals


class SecretsEmitter:
    connector_id = "secrets"

    def emit(self, data: Mapping[str, object]) -> list[ProblemSignal]:
        return [
            _signal(MissionType.SECURITY, finding, "secret_exposure", Severity.CRITICAL)
            for finding in _str_list(data, "findings")
        ]


class RuntimeEmitter:
    connector_id = "runtime"

    def emit(self, data: Mapping[str, object]) -> list[ProblemSignal]:
        signals: list[ProblemSignal] = []
        for label in _str_list(data, "workers_down"):
            signals.append(
                _signal(MissionType.OPERATIONS, label, "worker_down", Severity.CRITICAL)
            )
        for key in _str_list(data, "stalled_agents"):
            signals.append(_signal(MissionType.OPERATIONS, key, "agent_stalled", Severity.HIGH))
        return signals


def _severity(name: str) -> Severity:
    return {"critical": Severity.CRITICAL, "high": Severity.HIGH}.get(name.lower(), Severity.MEDIUM)


def default_emitters() -> tuple[ProblemEmitter, ...]:
    """The built-in emitters — one per connector domain. A new domain plugs in here."""
    return (
        WebsiteEmitter(),
        TlsEmitter(),
        HttpSecurityEmitter(),
        VulnerabilityEmitter(),
        SecretsEmitter(),
        RuntimeEmitter(),
    )


def emit_all(
    fetch: Callable[[str], Mapping[str, object] | None], emitters: tuple[ProblemEmitter, ...]
) -> list[ProblemSignal]:
    """Observe every emitter's connector and collect the signals. ``fetch`` returns a connector's OK
    data, or None when it is unavailable (no evidence → no signal — never fabricated)."""
    signals: list[ProblemSignal] = []
    for emitter in emitters:
        data = fetch(emitter.connector_id)
        if data is not None:
            # Stamp each signal with the connector that produced it — provenance for verification
            # (which connector to re-fetch), without touching the correlation identity.
            stamped = (replace(s, connector_id=emitter.connector_id) for s in emitter.emit(data))
            signals.extend(stamped)
    return signals
