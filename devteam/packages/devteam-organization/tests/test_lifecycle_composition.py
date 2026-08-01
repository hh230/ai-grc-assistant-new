"""The composition root (ADR 0065) — one assembled engine runs a problem end-to-end.

The Composition Root creates and wires every part (rule 1) from injected leaf primitives (rule 2);
these tests exercise the whole engine — detect → open → verify → close, and detect → escalate — with
fakes for the host's connectors and mission seams. Nothing here imports the daemon (rule 3).
"""

from __future__ import annotations

from collections.abc import Mapping

from devteam_organization.lifecycle import (
    Evidence,
    EvidenceSources,
    EvidenceState,
    ProblemState,
    RemediationPlan,
    build_lifecycle,
)
from devteam_organization.lifecycle.correlation import ProblemSignal
from devteam_organization.lifecycle.driver import EscalationTier


class _Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class _Verdict:
    def __init__(self) -> None:
        self.resolved = False


def _evidence(verdict: _Verdict) -> EvidenceSources:
    def reading(_signal: ProblemSignal) -> Evidence:
        state = EvidenceState.SATISFIED if verdict.resolved else EvidenceState.UNSATISFIED
        return Evidence("x", state)

    return EvidenceSources(
        connector_cleared=reading,
        ci_green=reading,
        runtime_healthy=reading,
        evidence_present=reading,
        human_confirmed=reading,
        documentation_reviewed=reading,
    )


def _connector_data(connector_id: str) -> Mapping[str, object] | None:
    if connector_id == "website":
        return {"endpoints": [{"url": "https://a", "ok": False}]}
    return None  # every other connector is unavailable → emits nothing


def test_composition_runs_a_problem_end_to_end() -> None:
    verdict = _Verdict()
    opened: list[tuple[ProblemSignal, RemediationPlan, int]] = []

    def open_mission(signal: ProblemSignal, plan: RemediationPlan, number: int) -> str | None:
        opened.append((signal, plan, number))
        return f"m{number}"

    composition = build_lifecycle(
        connector_data=_connector_data,
        evidence=_evidence(verdict),
        open_mission=open_mission,
        is_terminal=lambda _mission_id: True,
        escalate_mission=lambda _p, _t, _a: None,
        clock=_Clock(),
    )

    composition.sync()  # detect (website down) → open a gated remediation
    assert len(opened) == 1
    signal, plan, number = opened[0]
    assert number == 1
    assert plan.strategy_id == "infrastructure_change" and plan.consequential is True
    ref = signal.correlation_ref
    assert composition.coordinator.state(ref) is ProblemState.IN_PROGRESS
    assert composition.metrics_snapshot().active_problems == 1

    verdict.resolved = True
    composition.sync()  # verify (evidence + runtime clear) → close
    assert composition.coordinator.state(ref) is None  # resolved and closed
    assert composition.metrics_snapshot().active_problems == 0


def test_composition_escalates_after_the_attempt_cap() -> None:
    escalations: list[EscalationTier] = []

    composition = build_lifecycle(
        connector_data=_connector_data,
        evidence=_evidence(_Verdict()),  # never resolves
        open_mission=lambda _s, _p, number: f"m{number}",
        is_terminal=lambda _mission_id: True,
        escalate_mission=lambda _p, tier, _a: escalations.append(tier),
        max_attempts=3,
        clock=_Clock(),
    )

    for _ in range(4):  # three attempts, then the cap → escalate
        composition.sync()

    assert escalations == [EscalationTier.SUPERVISOR]
    assert composition.metrics_snapshot().escalation_count == 1
