"""The lifecycle Composition Root — the one place that assembles the engine (ADR 0065, S4b-2b-2b).

``build_lifecycle`` is the one factory that CREATES every part (the ledger, metrics, attempt store,
driver, resolver, coordinator, and the default registries/emitters/adapters) and wires them together
(rule 1). Every part is injected into the coordinator, which news-up nothing itself (rule 2). The
result is a plain ``LifecycleComposition`` the daemon HOSTS and calls — the daemon depends on the
lifecycle, never the reverse (rule 3): this package imports nothing from the daemon.

The leaf primitives (how a connector's data is fetched, how evidence is observed, how a mission is
opened / checked / escalated) are injected as callables, so the engine runs end-to-end under test
with fakes and, in production, with the real connectors + ``OrganizationRuntime`` from the host.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping

from devteam_chain import AttemptStore, ChainAlert, ChainAttempt

from devteam_organization.lifecycle.adapters import AdapterRegistry
from devteam_organization.lifecycle.coordinator import (
    LifecycleCoordinator,
    ResolutionResolver,
    Transition,
    TransitionSink,
    Trigger,
)
from devteam_organization.lifecycle.correlation import ProblemLedger, ProblemSignal
from devteam_organization.lifecycle.driver import (
    EscalationTier,
    LifecycleDriver,
    Problem,
)
from devteam_organization.lifecycle.emission import ProblemEmitter, default_emitters, emit_all
from devteam_organization.lifecycle.metrics import LifecycleMetrics, LifecycleMetricsSnapshot
from devteam_organization.lifecycle.resolution import (
    EvidenceSources,
    ResolutionCheckRegistry,
    default_resolution_registry,
)
from devteam_organization.lifecycle.strategies import default_strategy_registry
from devteam_organization.lifecycle.strategy import (
    RemediationPlan,
    RemediationPlanner,
    StrategyRegistry,
)

# How the host opens a remediation mission for a problem (its signal + the chosen plan + attempt
# number) — returns the opened mission id, or None when nothing is opened this pass.
OpenMission = Callable[[ProblemSignal, RemediationPlan, int], "str | None"]
# How the host escalates (opens a Supervisor/CEO mission). Matches the driver's escalation seam.
EscalateMission = Callable[[Problem, EscalationTier, ChainAlert], None]


class LifecycleComposition:
    """The assembled engine the daemon hosts. ``sync`` is one full pass: emit from connectors →
    observe, drain adapter events → notify, then reconcile — the single one-way flow into the
    coordinator. The ledger, metrics, and coordinator are exposed read-mostly for the dashboard."""

    def __init__(
        self,
        *,
        coordinator: LifecycleCoordinator,
        ledger: ProblemLedger,
        metrics: LifecycleMetrics,
        emitters: tuple[ProblemEmitter, ...],
        adapters: AdapterRegistry,
        connector_data: Callable[[str], Mapping[str, object] | None],
    ) -> None:
        self._coordinator = coordinator
        self._ledger = ledger
        self._metrics = metrics
        self._emitters = emitters
        self._adapters = adapters
        self._connector_data = connector_data

    def sync(self) -> None:
        """One host-driven pass (one-way flow, rule 4): detection → observe, events → notify, then
        reconcile. Detection hands ownership to the lifecycle; the coordinator owns all state."""
        for signal in emit_all(self._connector_data, self._emitters):
            self._coordinator.observe(signal, trigger=Trigger.CONNECTOR, source="emission")
        for event in self._adapters.drain_all():
            self._coordinator.notify(event)
        self._coordinator.tick()

    @property
    def coordinator(self) -> LifecycleCoordinator:
        return self._coordinator

    @property
    def ledger(self) -> ProblemLedger:
        return self._ledger

    @property
    def metrics(self) -> LifecycleMetrics:
        return self._metrics

    def metrics_snapshot(self) -> LifecycleMetricsSnapshot:
        return self._metrics.snapshot()


def build_lifecycle(
    *,
    connector_data: Callable[[str], Mapping[str, object] | None],
    evidence: EvidenceSources,
    open_mission: OpenMission,
    is_terminal: Callable[[str], bool],
    escalate_mission: EscalateMission,
    strategies: StrategyRegistry | None = None,
    resolution_checks: ResolutionCheckRegistry | None = None,
    emitters: tuple[ProblemEmitter, ...] | None = None,
    adapters: AdapterRegistry | None = None,
    on_transition: TransitionSink | None = None,
    max_attempts: int = 3,
    clock: Callable[[], float] = time.time,
) -> LifecycleComposition:
    """Assemble the whole lifecycle engine from injected leaf primitives (rule 1). The host supplies
    how to read connectors, observe evidence, and open/check/escalate missions; everything else is
    created and wired here."""
    strategy_registry = strategies if strategies is not None else default_strategy_registry()
    if resolution_checks is None:
        resolution_checks = default_resolution_registry(evidence)
    resolver = ResolutionResolver(strategy_registry, resolution_checks)
    planner = RemediationPlanner(strategy_registry)

    store = AttemptStore()
    ledger = ProblemLedger(clock=clock)
    metrics = LifecycleMetrics()

    def open_remediation(problem: Problem, number: int) -> str | None:
        active = ledger.find_active(problem.correlation_ref)
        if active is None:
            return None
        plan = planner.plan(active.signal)
        if plan is None:
            return None  # no strategy applies → a human owns it, do not open a mission
        return open_mission(active.signal, plan, number)

    def is_finished(attempt: ChainAttempt) -> bool:
        return is_terminal(attempt.mission_id)

    def record_transition(transition: Transition) -> None:
        metrics.record_transition(transition)  # metrics + audit both observe every transition
        if on_transition is not None:
            on_transition(transition)

    driver = LifecycleDriver(
        store,
        open_remediation=open_remediation,
        raise_escalation=escalate_mission,
        is_finished=is_finished,
        max_attempts=max_attempts,
        clock=clock,
    )
    coordinator = LifecycleCoordinator(
        driver,
        ledger,
        resolver,
        on_transition=record_transition,
        on_advance=metrics.record_advance,
        attempt_reset=store.forget,
        clock=clock,
    )
    return LifecycleComposition(
        coordinator=coordinator,
        ledger=ledger,
        metrics=metrics,
        emitters=emitters if emitters is not None else default_emitters(),
        adapters=adapters if adapters is not None else AdapterRegistry(),
        connector_data=connector_data,
    )
