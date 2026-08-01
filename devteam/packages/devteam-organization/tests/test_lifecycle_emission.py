"""Stateless problem emission (ADR 0065) — jobs observe and emit; the lifecycle owns the rest.

Rule 1 (detection ≠ ownership) + rule 2 (stateless): an emitter maps connector evidence to per-asset
ProblemSignals with no memory of its own; the same evidence always yields the same signals, and the
signals route straight into the strategy layer.
"""

from __future__ import annotations

from collections.abc import Mapping

from devteam_organization.lifecycle import Severity, default_strategy_registry, emit_all
from devteam_organization.lifecycle.emission import (
    HttpSecurityEmitter,
    RuntimeEmitter,
    SecretsEmitter,
    TlsEmitter,
    VulnerabilityEmitter,
    WebsiteEmitter,
    default_emitters,
)


def test_website_emitter_flags_each_failing_asset() -> None:
    data = {
        "endpoints": [
            {"url": "https://a", "ok": False},
            {"url": "https://b", "ok": True, "slow": True},
            {"url": "https://c", "ok": True},
        ]
    }
    signals = WebsiteEmitter().emit(data)
    by_asset = {s.asset: s for s in signals}
    assert set(by_asset) == {"https://a", "https://b"}  # healthy c emits nothing
    assert by_asset["https://a"].evidence_signature == "endpoint_down"
    assert by_asset["https://a"].severity is Severity.HIGH
    assert by_asset["https://b"].evidence_signature == "endpoint_slow"


def test_tls_and_http_security_emitters() -> None:
    tls = TlsEmitter().emit({"hosts": [{"host": "h1", "hostname_valid": False}]})
    assert tls[0].asset == "h1" and tls[0].evidence_signature == "tls_hostname"
    headers = HttpSecurityEmitter().emit(
        {"endpoints": [{"url": "https://x", "missing": ["CSP", "HSTS"]}]}
    )
    assert headers[0].evidence_signature == "missing_header:CSP+HSTS"  # sorted, per asset


def test_vulnerability_secrets_and_runtime_emitters() -> None:
    vulns = VulnerabilityEmitter().emit(
        {"high": [{"package": "lib-x", "severity": "critical"}]}
    )
    assert vulns[0].asset == "lib-x" and vulns[0].severity is Severity.CRITICAL
    secrets = SecretsEmitter().emit({"findings": ["aws-key in config"]})
    assert secrets[0].evidence_signature == "secret_exposure"
    assert secrets[0].severity is Severity.CRITICAL
    runtime = RuntimeEmitter().emit({"workers_down": ["org"], "stalled_agents": ["ciso"]})
    assert {s.evidence_signature for s in runtime} == {"worker_down", "agent_stalled"}


def test_emission_is_stateless_and_deterministic() -> None:
    emitter = WebsiteEmitter()
    data: Mapping[str, object] = {"endpoints": [{"url": "https://a", "ok": False}]}
    first = emitter.emit(data)
    second = emitter.emit(data)  # same evidence, no accumulated state → identical signals
    assert [s.correlation_ref for s in first] == [s.correlation_ref for s in second]


def test_emitted_signals_route_into_the_strategy_layer() -> None:
    registry = default_strategy_registry()
    header = HttpSecurityEmitter().emit({"endpoints": [{"url": "x", "missing": ["HSTS"]}]})[0]
    tls = TlsEmitter().emit({"hosts": [{"host": "h", "hostname_valid": False}]})[0]
    header_strategy = registry.select(header)
    tls_strategy = registry.select(tls)
    assert header_strategy is not None and header_strategy.id == "code_remediation"
    assert tls_strategy is not None and tls_strategy.id == "infrastructure_change"


def test_emit_all_skips_unavailable_connectors() -> None:
    available: dict[str, Mapping[str, object]] = {
        "website": {"endpoints": [{"url": "https://a", "ok": False}]},
        "secrets": {"findings": ["leak"]},
    }

    def fetch(connector_id: str) -> Mapping[str, object] | None:
        return available.get(connector_id)  # others (tls, vulnerability, …) → None (unavailable)

    signals = emit_all(fetch, default_emitters())
    assets = {s.asset for s in signals}
    assert assets == {"https://a", "leak"}  # only the two available connectors emitted
