"""Real end-to-end lifecycle scenarios (ADR 0065) — the acceptance suite for the engine.

Each scenario drives the assembled ``build_lifecycle`` engine through a realistic flow, faking only
the host's connectors and mission seams: website-down (with an approval gate), TLS expiry, a
compliance gap, a recurrence, a lost webhook, a daemon restart, and duplicate events.
"""

from __future__ import annotations

from collections.abc import Mapping

from devteam_organization.lifecycle import (
    Evidence,
    EvidenceSources,
    EvidenceState,
    LifecycleComposition,
    LifecycleEvent,
    LifecycleEventKind,
    ProblemSignal,
    ProblemState,
    RemediationPlan,
    Trigger,
    build_lifecycle,
)
from devteam_organization.lifecycle.driver import EscalationTier


class _Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class _World:
    """The mutable host the fakes read: which connectors show a problem, whether the evidence has
    cleared, and which missions have finished. Builds an engine wired to itself."""

    def __init__(self) -> None:
        self.clock = _Clock()
        self.connectors: dict[str, Mapping[str, object]] = {}
        self.resolved = False
        self.terminal: dict[str, bool] = {}
        self.opened: list[tuple[ProblemSignal, RemediationPlan, int]] = []
        self.escalations: list[EscalationTier] = []
        self.transitions: list[ProblemState] = []
        self._count = 0

    def _connector_data(self, connector_id: str) -> Mapping[str, object] | None:
        return self.connectors.get(connector_id)

    def _evidence(self) -> EvidenceSources:
        def reading(_signal: ProblemSignal) -> Evidence:
            state = EvidenceState.SATISFIED if self.resolved else EvidenceState.UNSATISFIED
            return Evidence("x", state)

        return EvidenceSources(
            connector_cleared=reading,
            ci_green=reading,
            runtime_healthy=reading,
            evidence_present=reading,
            human_confirmed=reading,
            documentation_reviewed=reading,
        )

    def _open(self, signal: ProblemSignal, plan: RemediationPlan, number: int) -> str | None:
        self._count += 1
        mission_id = f"m{self._count}"
        self.opened.append((signal, plan, number))
        self.terminal[mission_id] = False  # a fresh remediation is in flight (e.g. awaiting a gate)
        return mission_id

    def _is_terminal(self, mission_id: str) -> bool:
        return self.terminal.get(mission_id, True)

    def build(self, *, emitters: tuple[object, ...] | None = None) -> LifecycleComposition:
        return build_lifecycle(
            connector_data=self._connector_data,
            evidence=self._evidence(),
            open_mission=self._open,
            is_terminal=self._is_terminal,
            escalate_mission=lambda _p, tier, _a: self.escalations.append(tier),
            emitters=emitters,  # type: ignore[arg-type]
            on_transition=lambda t: self.transitions.append(t.to_state),
            clock=self.clock,
        )

    def finish_all_missions(self) -> None:
        for mission_id in self.terminal:
            self.terminal[mission_id] = True


class _ComplianceEmitter:
    connector_id = "compliance"

    def emit(self, data: Mapping[str, object]) -> list[ProblemSignal]:
        gaps = data.get("gaps")
        items = [g for g in gaps if isinstance(g, str)] if isinstance(gaps, list) else []
        return [
            ProblemSignal("compliance", gap, "policy_outdated", goal="close gap", summary="gap")
            for gap in items
        ]


def _website_down() -> dict[str, Mapping[str, object]]:
    return {"website": {"endpoints": [{"url": "https://a", "ok": False}]}}


# --- 1. Website down, with an approval gate ---


def test_scenario_1_website_down_through_the_full_lifecycle() -> None:
    world = _World()
    world.connectors = _website_down()
    engine = world.build()

    engine.sync()  # connector detects → emit → lifecycle owns → strategy → open a gated mission
    assert len(world.opened) == 1
    signal = world.opened[0][0]
    ref = signal.correlation_ref
    assert engine.coordinator.state(ref) is ProblemState.IN_PROGRESS

    engine.sync()  # the mission is not terminal (awaiting approval) → hold at the gate, no retry
    assert len(world.opened) == 1

    world.finish_all_missions()  # a human approves → the remediation lands
    world.resolved = True  # and the evidence clears
    engine.sync()  # verification succeeds → the problem closes

    assert engine.coordinator.state(ref) is None
    assert engine.metrics_snapshot().active_problems == 0  # metrics updated
    assert world.transitions == [  # the audit trail
        ProblemState.NEW,
        ProblemState.IN_PROGRESS,
        ProblemState.VERIFIED,
        ProblemState.CLOSED,
    ]


# --- 2. TLS expiry → infrastructure strategy, runtime verification ---


def test_scenario_2_tls_expiry_infrastructure_strategy() -> None:
    world = _World()
    world.connectors = {
        "tls": {"hosts": [{"host": "api.example.com", "hostname_valid": True, "expiring": True}]}
    }
    engine = world.build()

    engine.sync()
    signal, plan, _ = world.opened[0]
    assert plan.strategy_id == "infrastructure_change"  # security + tls → infrastructure change
    ref = signal.correlation_ref
    assert engine.coordinator.state(ref) is ProblemState.IN_PROGRESS

    world.resolved = True  # runtime + connector clear
    engine.sync()
    assert engine.coordinator.state(ref) is None  # closed after the evidence disappeared


# --- 3. Compliance gap → policy update needs the owner's approval ---


def test_scenario_3_compliance_gap_with_human_approval() -> None:
    world = _World()
    world.connectors = {"compliance": {"gaps": ["control:ISO-A.5.1"]}}
    engine = world.build(emitters=(_ComplianceEmitter(),))

    engine.sync()
    signal, plan, _ = world.opened[0]
    assert plan.strategy_id == "policy_update"
    assert plan.approval.approver == "policy_owner"  # a human (the policy owner) must approve
    ref = signal.correlation_ref
    assert engine.coordinator.state(ref) is ProblemState.IN_PROGRESS

    world.finish_all_missions()  # the policy owner approves
    world.resolved = True  # evidence collected + human confirmed
    engine.sync()
    assert engine.coordinator.state(ref) is None  # verified and closed


# --- 4. A recurrence after closure is a new lineage, not a resurrection ---


def test_scenario_4_recurring_problem_opens_a_fresh_lineage() -> None:
    world = _World()
    world.connectors = _website_down()
    engine = world.build()

    engine.sync()  # open
    ref = world.opened[0][0].correlation_ref
    world.resolved = True
    engine.sync()  # resolve + close
    assert engine.coordinator.state(ref) is None

    world.clock.now += 86_400.0  # a day later, the same problem recurs
    world.resolved = False
    engine.sync()

    problem = engine.ledger.find_active(ref)
    assert problem is not None and problem.first_seen == 1000.0 + 86_400.0  # a fresh lineage
    assert world.opened[-1][2] == 1  # attempt 1 again — the spent lineage was not revived


# --- 5. A lost webhook: the tick alone reconciles ---


def test_scenario_5_lost_webhook_is_reconciled_by_the_tick() -> None:
    world = _World()
    world.connectors = _website_down()
    engine = world.build()  # no adapters registered → no events will ever arrive

    engine.sync()  # only the tick
    ref = world.opened[0][0].correlation_ref
    assert engine.coordinator.state(ref) is ProblemState.IN_PROGRESS

    world.resolved = True
    engine.sync()  # the tick alone re-discovers the change
    assert engine.coordinator.state(ref) is None  # the correct state is reached with zero events


# --- 6. A daemon restart recovers the open problem ---


def test_scenario_6_daemon_restart_recovers_and_continues() -> None:
    world = _World()
    world.connectors = _website_down()
    before = world.build()
    before.sync()  # an open problem exists
    ref = world.opened[0][0].correlation_ref
    records = before.coordinator.export()
    assert records and records[0].state is ProblemState.IN_PROGRESS

    after = world.build()  # the daemon restarts: a fresh engine
    after.coordinator.recover(records)
    assert after.coordinator.state(ref) is ProblemState.IN_PROGRESS  # recovered, not from zero

    world.resolved = True
    after.sync()  # the lifecycle continues to closure
    assert after.coordinator.state(ref) is None


# --- 7. Duplicate events change nothing ---


def test_scenario_7_duplicate_events_are_idempotent() -> None:
    world = _World()
    world.connectors = _website_down()
    engine = world.build()
    engine.sync()  # open → IN_PROGRESS, mission m1 in flight
    ref = world.opened[0][0].correlation_ref
    world.terminal["m1"] = True  # m1 finished, so a fresh event can open the next attempt

    event = LifecycleEvent(LifecycleEventKind.EXECUTION_FINISHED, "evt-1", ref, Trigger.GITHUB)
    first = engine.coordinator.notify(event)
    assert first is not None and len(world.opened) == 2  # the event opened the next attempt

    second = engine.coordinator.notify(event)  # the SAME event again
    assert second is None  # idempotent — ignored
    assert len(world.opened) == 2  # no duplicate mission / attempt
