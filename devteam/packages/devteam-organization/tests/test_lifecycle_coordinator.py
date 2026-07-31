"""The lifecycle coordinator (ADR 0065) — the four owner rules for S4b.

Rule 1: one entry (``advance(problem, trigger)``), tagged with why. Rule 2: events are idempotent.
Rule 3: only generic events. Rule 4: every transition records its reason.
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
    """A mutable flag the evidence sources reflect, so a test can flip a problem to resolved."""

    def __init__(self) -> None:
        self.resolved = False


def _signal() -> ProblemSignal:
    return ProblemSignal(
        mission_type="security",  # + a code hint → the code_remediation strategy (connector + CI)
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
    verdict: _Verdict, *, attempts: int = 0
) -> tuple[LifecycleCoordinator, list[Transition], list[tuple[str, int]], list[str], list[str]]:
    store = AttemptStore()
    for number in range(1, attempts + 1):
        store.record(ChainAttempt(_REF, number, mission_id=f"m{number}"))
    opened: list[tuple[str, int]] = []
    escalated: list[str] = []
    reset: list[str] = []

    def open_remediation(problem: object, number: int) -> str | None:
        opened.append((_REF, number))
        return f"m{number}"

    def raise_escalation(problem: object, tier: object, alert: object) -> None:
        escalated.append(str(tier))

    driver = LifecycleDriver(
        store,
        open_remediation=open_remediation,
        raise_escalation=raise_escalation,
        is_finished=lambda _attempt: True,
        clock=_Clock(),
    )
    transitions: list[Transition] = []
    coordinator = LifecycleCoordinator(
        driver,
        ProblemLedger(clock=_Clock()),
        _resolver(verdict),
        on_transition=transitions.append,
        attempt_reset=reset.append,
        clock=_Clock(),
    )
    return coordinator, transitions, opened, escalated, reset


# --- rule 1: one entry, tagged with the trigger ---


def test_tick_and_events_record_their_trigger() -> None:
    verdict = _Verdict()
    coordinator, transitions, _opened, _esc, _reset = _build(verdict)
    coordinator.observe(_signal(), trigger=Trigger.CONNECTOR)
    coordinator.tick()  # polling advance

    assert transitions[0].to_state is ProblemState.NEW
    assert transitions[0].trigger is Trigger.CONNECTOR  # detection came from a connector
    assert transitions[1].to_state is ProblemState.IN_PROGRESS
    assert transitions[1].trigger is Trigger.POLL  # the tick advanced it


def test_notify_uses_the_events_trigger() -> None:
    verdict = _Verdict()
    coordinator, transitions, _opened, _esc, _reset = _build(verdict)
    coordinator.observe(_signal())
    event = LifecycleEvent(LifecycleEventKind.EVIDENCE_CHANGED, "e1", _REF, Trigger.GITHUB)
    coordinator.notify(event)

    in_progress = [t for t in transitions if t.to_state is ProblemState.IN_PROGRESS]
    assert in_progress and in_progress[0].trigger is Trigger.GITHUB


# --- rule 2: events are idempotent ---


def test_a_redelivered_event_changes_nothing() -> None:
    verdict = _Verdict()
    coordinator, transitions, opened, _esc, _reset = _build(verdict)
    coordinator.observe(_signal())
    event = LifecycleEvent(LifecycleEventKind.EXECUTION_FINISHED, "dup-1", _REF, Trigger.GITHUB)

    first = coordinator.notify(event)
    before = (len(transitions), len(opened))
    second = coordinator.notify(event)  # same event_id

    assert first is not None and second is None  # the duplicate is ignored
    assert (len(transitions), len(opened)) == before  # no new transition, no new attempt


def test_notify_on_unknown_problem_is_ignored() -> None:
    verdict = _Verdict()
    coordinator, transitions, _opened, _esc, _reset = _build(verdict)
    event = LifecycleEvent(LifecycleEventKind.EVIDENCE_CHANGED, "e1", "unknown:x", Trigger.RUNTIME)
    assert coordinator.notify(event) is None and transitions == []


# --- rule 3 + rule 4: generic events carry a reason; the full transition walk ---


def test_approval_granted_event_reasons_the_transition() -> None:
    verdict = _Verdict()
    coordinator, transitions, _opened, _esc, _reset = _build(verdict)
    coordinator.observe(_signal())
    event = LifecycleEvent(LifecycleEventKind.APPROVAL_GRANTED, "a1", _REF, Trigger.HUMAN)
    coordinator.notify(event)

    in_progress = [t for t in transitions if t.to_state is ProblemState.IN_PROGRESS]
    assert in_progress and in_progress[0].reason == "approval granted"  # generic kind → reason


def test_full_lifecycle_walk_records_each_reason() -> None:
    verdict = _Verdict()
    coordinator, transitions, _opened, _esc, reset = _build(verdict)
    coordinator.observe(_signal(), trigger=Trigger.CONNECTOR)
    coordinator.tick()  # unresolved → opens attempt 1
    verdict.resolved = True
    coordinator.tick()  # resolved → verified → closed

    states = [(t.to_state, t.reason) for t in transitions]
    assert states[0] == (ProblemState.NEW, "detected: missing_header")
    assert states[1] == (ProblemState.IN_PROGRESS, "remediation attempt 1 opened")
    assert states[2][0] is ProblemState.VERIFIED
    assert "connector" in states[2][1] and "ci" in states[2][1]  # multi-evidence detail
    assert states[3] == (ProblemState.CLOSED, "resolution policy satisfied")
    assert reset == [_REF]  # attempt lineage reset on close
    assert coordinator.state(_REF) is None  # closed problem leaves the live state map


def test_exhausted_attempts_escalate_with_a_reason() -> None:
    verdict = _Verdict()
    coordinator, transitions, opened, escalated, _reset = _build(verdict, attempts=3)
    coordinator.observe(_signal())
    coordinator.tick()  # at the cap, unresolved → escalate, not open

    assert opened == [] and escalated  # no new attempt; an escalation was raised
    escalations = [t for t in transitions if t.to_state is ProblemState.ESCALATED]
    assert escalations and "escalated to" in escalations[0].reason


# --- rule 4: provenance; rule 3: reconciliation; rule 2: out-of-order tolerance ---


def test_transition_records_the_event_source() -> None:
    verdict = _Verdict()
    coordinator, transitions, _opened, _esc, _reset = _build(verdict)
    coordinator.observe(_signal())
    event = LifecycleEvent(
        LifecycleEventKind.EXECUTION_FINISHED, "e1", _REF, Trigger.GITHUB, source="github-actions"
    )
    coordinator.notify(event)

    in_progress = [t for t in transitions if t.to_state is ProblemState.IN_PROGRESS]
    assert in_progress and in_progress[0].source == "github-actions"  # rule 4: provenance recorded


def test_reconciliation_converges_without_any_events() -> None:
    # Rule 3: no notify() at all — only the tick. Even if every webhook were lost, polling
    # re-discovers the change and the problem still reaches CLOSED (eventually consistent).
    verdict = _Verdict()
    coordinator, transitions, _opened, _esc, _reset = _build(verdict)
    coordinator.observe(_signal())
    coordinator.tick()  # opens attempt 1
    verdict.resolved = True
    coordinator.tick()  # reconciles to resolved → closed

    assert [t.to_state for t in transitions][-1] is ProblemState.CLOSED
    assert all(t.source in ("", "reconciliation") for t in transitions)  # closed by the reconciler


def test_a_late_event_after_close_is_ignored() -> None:
    # Rule 2: an event arriving after the problem closed targets nothing — ignored, state intact.
    verdict = _Verdict()
    coordinator, transitions, _opened, _esc, _reset = _build(verdict)
    coordinator.observe(_signal())
    coordinator.tick()
    verdict.resolved = True
    coordinator.tick()  # → CLOSED, the problem leaves the active set
    count_before = len(transitions)

    late = LifecycleEvent(LifecycleEventKind.EXECUTION_FINISHED, "late-1", _REF, Trigger.GITHUB)
    assert coordinator.notify(late) is None  # nothing active to advance
    assert len(transitions) == count_before  # no new transition; state was not corrupted
