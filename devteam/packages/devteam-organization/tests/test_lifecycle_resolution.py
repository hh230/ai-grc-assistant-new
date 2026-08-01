"""Resolution checks (ADR 0065) — plugin per strategy + multi-evidence.

These lock the owner's S4 principles 1 & 2: verification is a plugin (no if/else on mission type),
and closure combines several evidence sources — the originating evidence gone AND every success
signal (CI, runtime, human) — so one source is never assumed enough. A source that can't be observed
keeps the problem open.
"""

from __future__ import annotations

from devteam_organization.lifecycle import (
    Evidence,
    EvidenceResolutionCheck,
    EvidenceSource,
    EvidenceSources,
    EvidenceState,
    ProblemSignal,
    default_resolution_registry,
)

_SIGNAL = ProblemSignal("security", "host-a", "sig")


def _source(name: str, state: EvidenceState) -> EvidenceSource:
    return lambda _signal: Evidence(name, state)


def _sources(
    *,
    connector: EvidenceState = EvidenceState.SATISFIED,
    ci: EvidenceState = EvidenceState.SATISFIED,
    runtime: EvidenceState = EvidenceState.SATISFIED,
    evidence: EvidenceState = EvidenceState.SATISFIED,
    human: EvidenceState = EvidenceState.SATISFIED,
    docs: EvidenceState = EvidenceState.SATISFIED,
) -> EvidenceSources:
    return EvidenceSources(
        connector_cleared=_source("connector", connector),
        ci_green=_source("ci", ci),
        runtime_healthy=_source("runtime", runtime),
        evidence_present=_source("evidence", evidence),
        human_confirmed=_source("human", human),
        documentation_reviewed=_source("docs", docs),
    )


# --- the multi-evidence combination ---


def test_clearing_only_closes_when_no_execution_expected() -> None:
    check = EvidenceResolutionCheck("x", _source("connector", EvidenceState.SATISFIED))
    assert check.resolve(_SIGNAL).resolved is True  # human-ops: symptom gone, no exec proof needed


def test_clearing_plus_all_execution_satisfied_closes() -> None:
    check = EvidenceResolutionCheck(
        "x",
        _source("connector", EvidenceState.SATISFIED),
        (_source("ci", EvidenceState.SATISFIED),),
    )
    assert check.resolve(_SIGNAL).resolved is True


def test_execution_unsatisfied_keeps_it_open_even_if_symptom_cleared() -> None:
    # The multi-evidence point: the connector cleared, but CI is red → the fix failed, not resolved.
    check = EvidenceResolutionCheck(
        "x",
        _source("connector", EvidenceState.SATISFIED),
        (_source("ci", EvidenceState.UNSATISFIED),),
    )
    resolution = check.resolve(_SIGNAL)
    assert resolution.resolved is False
    assert resolution.execution_verified is False  # execution_failed


def test_execution_unavailable_waits() -> None:
    # CI pending / unreachable → cannot confirm success → wait, do not close.
    check = EvidenceResolutionCheck(
        "x",
        _source("connector", EvidenceState.SATISFIED),
        (_source("ci", EvidenceState.UNAVAILABLE),),
    )
    assert check.resolve(_SIGNAL).resolved is False


def test_clearing_unsatisfied_or_unavailable_does_not_close() -> None:
    exec_ok = (_source("ci", EvidenceState.SATISFIED),)
    persists = EvidenceResolutionCheck("x", _source("c", EvidenceState.UNSATISFIED), exec_ok)
    unobserved = EvidenceResolutionCheck("x", _source("c", EvidenceState.UNAVAILABLE), exec_ok)
    assert persists.resolve(_SIGNAL).resolved is False  # the condition still present
    assert unobserved.resolve(_SIGNAL).resolved is False  # connector down ≠ resolved


# --- the registry is a plugin (no if/else) ---


def test_registry_looks_up_by_strategy_and_is_extensible() -> None:
    registry = default_resolution_registry(_sources())
    assert registry.for_strategy("code_remediation") is not None
    assert registry.for_strategy("unknown_strategy") is None

    custom = EvidenceResolutionCheck("custom", _source("connector", EvidenceState.SATISFIED))
    registry.register("new_domain", custom)  # a new domain is just a registration
    assert registry.for_strategy("new_domain") is custom


def test_default_registry_covers_every_built_in_strategy() -> None:
    registry = default_resolution_registry(_sources())
    for strategy_id in (
        "code_remediation",
        "infrastructure_change",
        "evidence_collection",
        "policy_update",
        "documentation",
        "risk_acceptance",
        "runbook_execution",
    ):
        assert registry.for_strategy(strategy_id) is not None


# --- the built-in checks combine the owner's evidence sources ---


def test_code_remediation_needs_connector_and_ci() -> None:
    check = default_resolution_registry(_sources(connector=EvidenceState.SATISFIED)).for_strategy(
        "code_remediation"
    )
    assert check is not None and check.resolve(_SIGNAL).resolved is True  # connector + CI green
    red_ci = default_resolution_registry(
        _sources(connector=EvidenceState.SATISFIED, ci=EvidenceState.UNSATISFIED)
    ).for_strategy("code_remediation")
    assert red_ci is not None and red_ci.resolve(_SIGNAL).resolved is False  # CI red → not resolved


def test_policy_update_needs_evidence_and_human() -> None:
    without_human = default_resolution_registry(
        _sources(evidence=EvidenceState.SATISFIED, human=EvidenceState.UNAVAILABLE)
    ).for_strategy("policy_update")
    assert without_human is not None and without_human.resolve(_SIGNAL).resolved is False
    with_human = default_resolution_registry(_sources()).for_strategy("policy_update")
    assert with_human is not None and with_human.resolve(_SIGNAL).resolved is True


def test_risk_acceptance_closes_on_human_confirmation_alone() -> None:
    confirmed = default_resolution_registry(_sources()).for_strategy("risk_acceptance")
    assert confirmed is not None and confirmed.resolve(_SIGNAL).resolved is True
    pending = default_resolution_registry(
        _sources(human=EvidenceState.UNAVAILABLE)
    ).for_strategy("risk_acceptance")
    assert pending is not None and pending.resolve(_SIGNAL).resolved is False
