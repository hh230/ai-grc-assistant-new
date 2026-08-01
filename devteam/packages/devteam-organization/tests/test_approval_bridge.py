"""S5a-bridge — the daemon gate + the decision adapter, end to end over the real driver.

The DoD in-process (the live daemon run is S5-live): a consequential problem opens a gate and WAITS
(no mission); a human grant recorded in the shared store is drained by ``ApprovalDecisionAdapter``
into ``notify`` → the mission opens → the problem resolves → closes → the gate is cleared so a
recurrence re-gates. The Core is used exactly as frozen (only the ``open_mission`` seam + a
registered adapter — both host extension points).
"""

from __future__ import annotations

from pathlib import Path

from devteam_approval import Actor, ApprovalService, ApprovalStatus, FileApprovalStore
from devteam_organization.approval_adapter import ApprovalDecisionAdapter
from devteam_organization.lifecycle import (
    AdapterRegistry,
    Evidence,
    EvidenceSources,
    EvidenceState,
    LifecycleComposition,
    ProblemSignal,
    ProblemState,
    RemediationPlan,
    Transition,
    Trigger,
    build_lifecycle,
)
from devteam_organization.lifecycle_host import build_approval_gate

_CEO = Actor(actor_id="ceo", name="Chief", role="policy_owner")


class _Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class _Verdict:
    def __init__(self) -> None:
        self.resolved = False


def _signal() -> ProblemSignal:
    # operations → a gated strategy → a consequential plan → the gate engages
    return ProblemSignal(
        mission_type="operations",
        asset="example.com",
        evidence_signature="site_down",
        goal="restore example.com",
        summary="example.com is unreachable",
    )


def _evidence(verdict: _Verdict) -> EvidenceSources:
    def source(name: str) -> Evidence:
        state = EvidenceState.SATISFIED if verdict.resolved else EvidenceState.UNSATISFIED
        return Evidence(name, state)

    return EvidenceSources(
        connector_cleared=lambda _s: source("connector"),
        ci_green=lambda _s: source("ci"),
        runtime_healthy=lambda _s: source("runtime"),
        evidence_present=lambda _s: source("evidence"),
        human_confirmed=lambda _s: source("human"),
        documentation_reviewed=lambda _s: source("docs"),
    )


def _build(
    tmp_path: Path, verdict: _Verdict
) -> tuple[LifecycleComposition, AdapterRegistry, ApprovalService, list[int]]:
    service = ApprovalService(FileApprovalStore(tmp_path / "approvals.json"))
    opened: list[int] = []

    def open_now(signal: ProblemSignal, plan: RemediationPlan, number: int) -> str:
        opened.append(number)
        return f"m{number}"

    def clear_on_close(transition: Transition) -> None:  # mirrors the host's on_transition
        if transition.to_state is ProblemState.CLOSED:
            service.clear_target(transition.correlation_ref)

    adapters = AdapterRegistry()
    adapters.register(ApprovalDecisionAdapter(service))
    comp = build_lifecycle(
        connector_data=lambda _cid: None,
        evidence=_evidence(verdict),
        open_mission=build_approval_gate(service, open_now),
        is_terminal=lambda _mid: False,  # the mission stays in flight; resolution is verdict-driven
        escalate_mission=lambda _p, _t, _a: None,
        adapters=adapters,
        on_transition=clear_on_close,
        clock=_Clock(),
    )
    return comp, adapters, service, opened


def _pump(comp: LifecycleComposition, adapters: AdapterRegistry) -> None:
    """One sync pass without the connector emitters: drain the adapter → notify, then reconcile."""
    for event in adapters.drain_all():
        comp.coordinator.notify(event)
    comp.coordinator.tick()


def test_full_human_in_the_loop_cycle(tmp_path: Path) -> None:
    verdict = _Verdict()
    comp, adapters, service, opened = _build(tmp_path, verdict)
    ref = "operations:example.com:site_down"

    # 1) detected → the gate opens a pending request and the problem WAITS (no mission runs)
    comp.coordinator.observe(_signal(), trigger=Trigger.CONNECTOR)
    _pump(comp, adapters)
    pending = service.pending()
    assert len(pending) == 1 and pending[0].target_ref == ref
    # the Strategy's approval rode through to the gate: a real requirement + a human-readable reason
    assert pending[0].policy.requirement == "standard"
    assert "example.com is unreachable" in pending[0].policy.reason
    assert opened == []  # nothing executed — awaiting a human
    assert comp.coordinator.state(ref) is ProblemState.NEW

    # 2) a human grants it (exactly what the Approval API records into the shared store)
    service.approve(pending[0].id, actor=_CEO, comment="restart approved")

    # 3) the adapter drains the grant → notify(APPROVAL_GRANTED) → the mission finally opens
    _pump(comp, adapters)
    assert opened == [1]  # executed once, only after approval
    assert comp.coordinator.state(ref) is ProblemState.IN_PROGRESS

    # 4) the remediation clears the evidence → the problem verifies and closes
    verdict.resolved = True
    _pump(comp, adapters)
    assert comp.coordinator.state(ref) is None  # closed → left the live map
    assert service.for_target(ref) is None  # gate cleared on close → a recurrence re-gates


def test_a_redelivered_grant_opens_the_mission_only_once(tmp_path: Path) -> None:
    verdict = _Verdict()
    comp, adapters, service, opened = _build(tmp_path, verdict)

    comp.coordinator.observe(_signal())
    _pump(comp, adapters)
    request = service.pending()[0]
    service.approve(request.id, actor=_CEO)

    _pump(comp, adapters)  # applies the grant
    _pump(comp, adapters)  # the same decision is still in the store — must NOT re-open
    _pump(comp, adapters)
    assert opened == [1]  # idempotent: one grant, one execution, regardless of re-drains


def test_rejection_never_opens_the_mission(tmp_path: Path) -> None:
    verdict = _Verdict()
    comp, adapters, service, opened = _build(tmp_path, verdict)
    ref = "operations:example.com:site_down"

    comp.coordinator.observe(_signal())
    _pump(comp, adapters)
    request = service.pending()[0]
    service.reject(request.id, actor=_CEO, comment="not now")

    _pump(comp, adapters)
    assert opened == []  # a rejected consequential remediation is never executed
    recorded = service.for_target(ref)
    assert recorded is not None and recorded.status is ApprovalStatus.REJECTED  # decision recorded
