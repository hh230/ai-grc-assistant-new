"""Problem correlation (ADR 0065) — identity is (Mission Type + Asset + Evidence Signature).

These lock the owner's second principle: a problem is tracked correctly across all domains — the
same condition on different assets is a different lineage, the same condition on one asset dedups,
and domains never collide — and a problem re-arms (a fresh lineage) after it is resolved.
"""

from __future__ import annotations

from devteam_organization.lifecycle import ProblemLedger, ProblemSignal
from devteam_protocol import AgentCapability


class _Clock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _signal(mission_type: str, asset: str, evidence: str) -> ProblemSignal:
    return ProblemSignal(
        mission_type=mission_type,
        asset=asset,
        evidence_signature=evidence,
        goal=f"resolve {mission_type} on {asset}",
        summary=f"{mission_type}/{asset}",
        stages=(AgentCapability.STRATEGY, AgentCapability.DELIVERY),
    )


# --- the correlation identity (type + asset + evidence) ---


def test_correlation_ref_is_type_asset_evidence() -> None:
    signal = _signal("tls_remediation", "api.example.com", "expiry")
    assert signal.correlation_ref == "tls_remediation:api.example.com:expiry"


def test_type_and_asset_are_sanitized_colon_free() -> None:
    # A stray ':' in the type/asset must not split the key; the free-form evidence keeps its colons.
    signal = ProblemSignal("a:b", "host:1", "CVE-2024-1:high")
    assert signal.correlation_ref == "a_b:host_1:CVE-2024-1:high"


def test_same_condition_different_asset_is_a_different_lineage() -> None:
    a = _signal("tls_remediation", "host-a", "expiry")
    b = _signal("tls_remediation", "host-b", "expiry")
    assert a.correlation_ref != b.correlation_ref  # host-a ≠ host-b


def test_different_domain_same_asset_is_a_different_lineage() -> None:
    vuln = _signal("dependency_vuln", "service-x", "CVE-1")
    gap = _signal("compliance_gap", "service-x", "CVE-1")
    assert vuln.correlation_ref != gap.correlation_ref  # domains never collide


def test_same_condition_same_asset_is_one_lineage() -> None:
    first = _signal("security_headers", "www.example.com", "missing:HSTS")
    again = _signal("security_headers", "www.example.com", "missing:HSTS")
    assert first.correlation_ref == again.correlation_ref  # a recurrence dedups


# --- the ledger (register / dedup / active-set / re-arm) ---


def test_observe_registers_new_and_dedups_existing() -> None:
    ledger = ProblemLedger(clock=_Clock())
    signal = _signal("tls_remediation", "host-a", "expiry")

    assert ledger.observe(signal) is True  # new problem
    assert ledger.observe(signal) is False  # same ref → not new (the lifecycle already has it)
    assert len(ledger.active()) == 1


def test_observe_refreshes_last_seen_and_latest_signal() -> None:
    clock = _Clock(100.0)
    ledger = ProblemLedger(clock=clock)
    ledger.observe(_signal("tls_remediation", "host-a", "expiry"))
    clock.now = 250.0
    updated = ProblemSignal("tls_remediation", "host-a", "expiry", summary="now urgent")
    ledger.observe(updated)

    problem = ledger.find_active("tls_remediation:host-a:expiry")
    assert problem is not None
    assert problem.first_seen == 100.0 and problem.last_seen == 250.0
    assert problem.signal.summary == "now urgent"


def test_active_holds_multiple_domains_oldest_first() -> None:
    clock = _Clock(10.0)
    ledger = ProblemLedger(clock=clock)
    ledger.observe(_signal("tls_remediation", "host-a", "expiry"))
    clock.now = 20.0
    ledger.observe(_signal("compliance_gap", "control:ISO-A.5.1", "unmet"))
    clock.now = 30.0
    ledger.observe(_signal("dependency_vuln", "service-x", "CVE-1"))

    refs = [problem.correlation_ref for problem in ledger.active()]
    assert refs == [
        "tls_remediation:host-a:expiry",
        "compliance_gap:control_ISO-A.5.1:unmet",
        "dependency_vuln:service-x:CVE-1",
    ]  # three domains coexist, ordered by first_seen


def test_deactivate_then_reobserve_is_a_fresh_lineage() -> None:
    clock = _Clock(100.0)
    ledger = ProblemLedger(clock=clock)
    signal = _signal("tls_remediation", "host-a", "expiry")
    ledger.observe(signal)

    assert ledger.deactivate(signal.correlation_ref) is True
    assert ledger.is_active(signal.correlation_ref) is False
    assert ledger.deactivate(signal.correlation_ref) is False  # already gone

    clock.now = 500.0
    assert ledger.observe(signal) is True  # a recurrence after closure is a NEW problem
    problem = ledger.find_active(signal.correlation_ref)
    assert problem is not None and problem.first_seen == 500.0  # fresh lineage, not a resurrection
