"""Lifecycle operational maturity (ADR 0065) — recoverability, tick-independence, metrics.

Rule 1: the coordinator rebuilds its state from persistence, not memory. Rule 2: execution happens
on notify, not only on the tick. Rule 3: the lifecycle is measurable (active / MTTV / MTTC /
retries / escalations / verification failures / event latency).
"""

from __future__ import annotations

from devteam_chain import AttemptStore, ChainAttempt
from devteam_organization.lifecycle import (
    Evidence,
    EvidenceSources,
    EvidenceState,
    LifecycleCoordinator,
    LifecycleDriver,
    LifecycleEvent,
    LifecycleEventKind,
    LifecycleMetrics,
    ProblemLedger,
    ProblemSignal,
    ProblemState,
    ResolutionResolver,
    Trigger,
    default_resolution_registry,
    default_strategy_registry,
)

_REF = "security:host-a:missing_header"


class _Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class _Verdict:
    def __init__(self) -> None:
        self.resolved = False
        self.exec_failed = False  # clearing evidence gone, but execution (CI) failed


def _signal() -> ProblemSignal:
    return ProblemSignal("security", "host-a", "missing_header", goal="g", summary="s")


def _resolver(verdict: _Verdict) -> ResolutionResolver:
    def state(is_ci: bool) -> EvidenceState:
        if verdict.resolved:
            return EvidenceState.SATISFIED
        if verdict.exec_failed:
            return EvidenceState.UNSATISFIED if is_ci else EvidenceState.SATISFIED
        return EvidenceState.UNSATISFIED

    def source(name: str, *, is_ci: bool = False) -> Evidence:
        return Evidence(name, state(is_ci))

    sources = EvidenceSources(
        connector_cleared=lambda _s: source("connector"),
        ci_green=lambda _s: source("ci", is_ci=True),
        runtime_healthy=lambda _s: source("runtime"),
        evidence_present=lambda _s: source("evidence"),
        human_confirmed=lambda _s: source("human"),
        documentation_reviewed=lambda _s: source("docs"),
    )
    return ResolutionResolver(default_strategy_registry(), default_resolution_registry(sources))


def _build(
    verdict: _Verdict, *, clock: _Clock | None = None, attempts: int = 0
) -> tuple[LifecycleCoordinator, LifecycleMetrics, _Clock]:
    store = AttemptStore()
    for number in range(1, attempts + 1):
        store.record(ChainAttempt(_REF, number, mission_id=f"m{number}"))
    clk = clock if clock is not None else _Clock()
    driver = LifecycleDriver(
        store,
        open_remediation=lambda _p, number: f"m{number}",
        raise_escalation=lambda _p, _t, _a: None,
        is_finished=lambda _attempt: True,
        clock=clk,
    )
    metrics = LifecycleMetrics()
    coordinator = LifecycleCoordinator(
        driver,
        ProblemLedger(clock=clk),
        _resolver(verdict),
        on_transition=metrics.record_transition,
        on_advance=metrics.record_advance,
        clock=clk,
    )
    return coordinator, metrics, clk


# --- rule 1: recoverability ---


def test_recover_rebuilds_state_from_persistence() -> None:
    source, _m, _c = _build(_Verdict())
    source.observe(_signal())
    source.tick()  # → IN_PROGRESS
    records = source.export()
    assert len(records) == 1 and records[0].state is ProblemState.IN_PROGRESS

    recovered, _m2, _c2 = _build(_Verdict())
    recovered.recover(records)  # rebuild from the records, not memory
    assert recovered.state(_REF) is ProblemState.IN_PROGRESS  # continued, not restarted
    assert len(recovered.export()) == 1  # the problem is active in the ledger again


# --- rule 2: execution is not tied to the tick ---


def test_notify_advances_without_a_tick() -> None:
    coordinator, _m, _c = _build(_Verdict())
    coordinator.observe(_signal())
    event = LifecycleEvent(LifecycleEventKind.EVIDENCE_CHANGED, "e1", _REF, Trigger.GITHUB)
    coordinator.notify(event)  # no tick() at all
    assert coordinator.state(_REF) is ProblemState.IN_PROGRESS  # execution ran on notify


# --- rule 3: metrics ---


def test_metrics_track_active_verify_and_close() -> None:
    verdict = _Verdict()
    clock = _Clock(1000.0)
    coordinator, metrics, _c = _build(verdict, clock=clock)
    coordinator.observe(_signal())  # NEW at 1000
    coordinator.tick()  # IN_PROGRESS at 1000
    assert metrics.snapshot().active_problems == 1
    clock.now = 1100.0
    verdict.resolved = True
    coordinator.tick()  # VERIFIED + CLOSED at 1100

    snap = metrics.snapshot()
    assert snap.active_problems == 0
    assert snap.mean_time_to_verify == 100.0
    assert snap.mean_time_to_close == 100.0


def test_metrics_count_retries_and_verification_failures() -> None:
    verdict = _Verdict()
    verdict.exec_failed = True  # a remediation runs but CI stays red
    coordinator, metrics, _c = _build(verdict)
    coordinator.observe(_signal())
    coordinator.tick()  # attempt 1 opened; execution failed
    coordinator.tick()  # attempt 2 opened (a retry); execution failed again

    snap = metrics.snapshot()
    assert snap.retry_count == 1  # attempt 2 is the retry
    assert snap.verification_failures == 2  # both advances saw a failed execution


def test_metrics_count_escalations() -> None:
    coordinator, metrics, _c = _build(_Verdict(), attempts=3)  # at the cap
    coordinator.observe(_signal())
    coordinator.tick()  # unresolved at the cap → escalate
    assert metrics.snapshot().escalation_count == 1


def test_metrics_mean_event_latency() -> None:
    metrics = LifecycleMetrics()
    metrics.record_event(10.0)
    metrics.record_event(30.0)
    snap = metrics.snapshot()
    assert snap.events_processed == 2 and snap.mean_event_latency_ms == 20.0
