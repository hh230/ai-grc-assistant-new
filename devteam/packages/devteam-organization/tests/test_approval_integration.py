"""S5 Phase 2 — the Approval Domain drives the frozen lifecycle through ``notify()`` only.

The proof the owner asked for, and nothing more: Grant resumes, Reject follows the coordinator's own
policy, Cancel emits no event and leaves the coordinator untouched. The adapter is a translation
layer — every lifecycle decision is the coordinator's — so the Core is used exactly as frozen (no
edit to driver / coordinator / correlation / strategy / resolution).
"""

from __future__ import annotations

from collections.abc import Callable

from devteam_approval import Actor, ApprovalPolicy, ApprovalService, ApprovalStatus
from devteam_chain import AttemptStore, ChainAttempt
from devteam_organization.approval_adapter import ApprovalLifecycleAdapter
from devteam_organization.lifecycle import (
    Evidence,
    EvidenceSources,
    EvidenceState,
    LifecycleCoordinator,
    LifecycleDriver,
    LifecycleEventKind,
    ProblemLedger,
    ProblemSignal,
    ProblemState,
    ResolutionResolver,
    Transition,
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
    """A mutable flag the evidence sources reflect, so a test can clear a problem's evidence."""

    def __init__(self) -> None:
        self.resolved = False


def _counter(prefix: str = "") -> Callable[[], str]:
    box = {"n": 0}

    def _next() -> str:
        box["n"] += 1
        return f"{prefix}{box['n']}"

    return _next


def _signal() -> ProblemSignal:
    return ProblemSignal(
        mission_type="security",
        asset="host-a",
        evidence_signature="missing_header",
        goal="fix the header",
        summary="missing security header",
    )


def _resolver(verdict: _Verdict) -> ResolutionResolver:
    def source(name: str) -> Evidence:
        state = EvidenceState.SATISFIED if verdict.resolved else EvidenceState.UNSATISFIED
        return Evidence(name, state)

    sources = EvidenceSources(
        connector_cleared=lambda _s: source("connector"),
        ci_green=lambda _s: source("ci"),
        runtime_healthy=lambda _s: source("runtime"),
        evidence_present=lambda _s: source("evidence"),
        human_confirmed=lambda _s: source("human"),
        documentation_reviewed=lambda _s: source("docs"),
    )
    return ResolutionResolver(default_strategy_registry(), default_resolution_registry(sources))


def _build(
    verdict: _Verdict,
) -> tuple[LifecycleCoordinator, list[tuple[str, int]], list[Transition]]:
    store = AttemptStore()
    opened: list[tuple[str, int]] = []

    def open_remediation(problem: object, number: int) -> str | None:
        opened.append((_REF, number))
        store.record(ChainAttempt(_REF, number, mission_id=f"m{number}"))
        return f"m{number}"

    driver = LifecycleDriver(
        store,
        open_remediation=open_remediation,
        raise_escalation=lambda problem, tier, alert: None,
        is_finished=lambda _attempt: True,
        clock=_Clock(),
    )
    transitions: list[Transition] = []
    coordinator = LifecycleCoordinator(
        driver,
        ProblemLedger(clock=_Clock()),
        _resolver(verdict),
        on_transition=transitions.append,
        clock=_Clock(),
    )
    return coordinator, opened, transitions


def _gate(coordinator: LifecycleCoordinator) -> tuple[ApprovalService, ApprovalLifecycleAdapter]:
    service = ApprovalService(new_id=_counter("id-"), clock=_Clock())
    return service, ApprovalLifecycleAdapter(coordinator)


# --- scenario 1: Grant → the coordinator resumes and closes ---


def test_grant_resumes_the_problem() -> None:
    verdict = _Verdict()
    coordinator, _opened, transitions = _build(verdict)
    coordinator.observe(_signal(), trigger=Trigger.CONNECTOR)
    coordinator.tick()  # opens a remediation attempt → IN_PROGRESS
    assert coordinator.state(_REF) is ProblemState.IN_PROGRESS

    service, adapter = _gate(coordinator)
    request = service.create(target_ref=_REF, resume_token="r", policy=ApprovalPolicy("standard"))

    verdict.resolved = True  # the approved remediation ran and cleared the evidence
    ceo = Actor(actor_id="ceo", name="Chief", role="ceo")
    outcome = adapter.dispatch(service.approve(request.id, actor=ceo, comment="ship"))

    # the decision reached the coordinator through notify(), which resumed → verified → closed
    assert outcome is not None
    closed = [t for t in transitions if t.to_state is ProblemState.CLOSED]
    assert closed and closed[0].source == "approval"  # the closure was driven by the approval
    assert coordinator.state(_REF) is None  # a closed problem leaves the live state map


# --- scenario 2: Reject → the coordinator follows its own policy ---


def test_reject_lets_the_coordinator_follow_its_policy() -> None:
    verdict = _Verdict()  # evidence stays present
    coordinator, opened, _transitions = _build(verdict)
    coordinator.observe(_signal())
    coordinator.tick()  # attempt 1 → IN_PROGRESS
    assert opened == [(_REF, 1)]

    service, adapter = _gate(coordinator)
    request = service.create(target_ref=_REF, resume_token="r", policy=ApprovalPolicy("standard"))
    ceo = Actor(actor_id="ceo", name="Chief", role="ceo")
    outcome = adapter.dispatch(service.reject(request.id, actor=ceo, comment="no"))

    # the adapter took no decision; the coordinator advanced by its OWN policy (next attempt opened)
    assert outcome is not None
    assert outcome.attempt is not None and outcome.attempt.attempt_number == 2
    assert opened == [(_REF, 1), (_REF, 2)]  # the driver, not the adapter, opened the next attempt
    assert coordinator.state(_REF) is ProblemState.IN_PROGRESS


# --- scenario 3: Cancel → no event, the coordinator is untouched ---


def test_cancel_emits_no_event_and_leaves_the_coordinator_unchanged() -> None:
    verdict = _Verdict()
    coordinator, _opened, transitions = _build(verdict)
    coordinator.observe(_signal())
    coordinator.tick()  # IN_PROGRESS

    service, adapter = _gate(coordinator)
    service.create(target_ref=_REF, resume_token="r", policy=ApprovalPolicy("standard"))

    verdict.resolved = True  # the problem resolves out-of-band → the target closes
    coordinator.tick()
    assert any(t.to_state is ProblemState.CLOSED for t in transitions)  # the target closed
    transitions_before = list(transitions)

    cancelled = service.cancel_for_target(_REF)  # the gate is cancelled because its target closed
    assert cancelled is not None and cancelled.status is ApprovalStatus.CANCELLED
    assert adapter.dispatch(cancelled) is None  # CANCELLED never wakes the lifecycle
    assert transitions == transitions_before  # no new transition — the coordinator is unchanged


# --- expiry maps to a rejected event, so the Core needs no new event kind ---


def test_expiry_translates_to_a_rejected_event() -> None:
    verdict = _Verdict()
    coordinator, _opened, _transitions = _build(verdict)
    service = ApprovalService(new_id=_counter("id-"), clock=_Clock(2000.0))
    adapter = ApprovalLifecycleAdapter(coordinator)

    service.create(
        target_ref=_REF, resume_token="r", policy=ApprovalPolicy("s"), expires_at=1500.0
    )
    (expired,) = service.expire_due()

    event = adapter.to_event(expired)
    assert event is not None
    assert event.kind is LifecycleEventKind.APPROVAL_REJECTED  # reuse — no new Core event kind
    assert event.trigger is Trigger.TIMER  # a deadline, not a human decision
    assert event.detail == "expired" and event.event_id == f"{expired.id}:expired"
