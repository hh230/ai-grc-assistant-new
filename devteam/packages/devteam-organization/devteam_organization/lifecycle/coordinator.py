"""The lifecycle coordinator — the single entry point that advances problems (ADR 0065).

Four owner rules (2026-07-30), load-bearing because they are hard to change after daemon wiring:

1. **One entry, tagged with *why*.** Polling and events go through ``advance(problem, trigger)``;
   ``trigger`` (POLL / CONNECTOR / GITHUB / RUNTIME / HUMAN / TIMER) records the source of change,
   not just that it changed. ``tick`` polls with POLL; ``notify`` uses the event's trigger.
2. **Events are idempotent.** A re-delivered event (same ``event_id``) is ignored — no state change,
   no new attempt.
3. **Generic events only.** The coordinator understands ``EvidenceChanged / ExecutionFinished /
   ApprovalGranted / ApprovalRejected / RuntimeRecovered`` — never GitHub/connector specifics. An
   adapter translates the external system into these.
4. **Every transition records its reason.** A problem moves NEW → IN_PROGRESS → VERIFIED → CLOSED
   (or ESCALATED), and each move carries *why* (``approval granted``; ``connector cleared + ci
   green``; ``resolution policy satisfied``) — for the audit trail (CLAUDE.md §19).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum

from devteam_organization.lifecycle.correlation import ActiveProblem, ProblemLedger, ProblemSignal
from devteam_organization.lifecycle.driver import (
    LifecycleDriver,
    LifecycleOutcome,
    LifecycleStatus,
    Problem,
    Resolution,
)
from devteam_organization.lifecycle.resolution import ResolutionCheckRegistry
from devteam_organization.lifecycle.strategy import StrategyRegistry


class Trigger(str, Enum):
    """Why an advance ran — the source class, for the transition reason (never source-specific)."""

    POLL = "poll"  # the fallback tick
    CONNECTOR = "connector"
    GITHUB = "github"
    RUNTIME = "runtime"
    HUMAN = "human"
    TIMER = "timer"


class LifecycleEventKind(str, Enum):
    """Source-neutral events. Adapters map external signals to these — the coordinator never
    sees a GitHub payload or a connector schema (rule 3)."""

    EVIDENCE_CHANGED = "evidence_changed"
    EXECUTION_FINISHED = "execution_finished"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    RUNTIME_RECOVERED = "runtime_recovered"


@dataclass(frozen=True)
class LifecycleEvent:
    """A generic lifecycle event. ``event_id`` is the idempotency identity (a webhook delivery id,
    a CI run id); a re-delivery with the same id is ignored. ``correlation_ref`` names the target
    problem (an adapter resolves it). ``trigger`` records the source class."""

    kind: LifecycleEventKind
    event_id: str
    correlation_ref: str
    trigger: Trigger
    source: str = ""  # the concrete emitter, e.g. "github-actions" (rule 4 — provenance)
    detail: str = ""


class ProblemState(str, Enum):
    """A problem's lifecycle state (rule 4), distinct from the per-advance ``LifecycleStatus``:
    the durable state whose transitions are recorded with reasons."""

    NEW = "new"  # detected, no remediation yet
    IN_PROGRESS = "in_progress"  # a remediation attempt is open / executing / awaiting approval
    VERIFIED = "verified"  # resolution confirmed (evidence gone + execution proven)
    CLOSED = "closed"  # deactivated — done
    ESCALATED = "escalated"  # automated attempts exhausted / escalated


@dataclass(frozen=True)
class Transition:
    """One recorded state change: from → to, why, by which trigger + source (rule 4), when."""

    correlation_ref: str
    from_state: ProblemState | None
    to_state: ProblemState
    reason: str
    trigger: Trigger
    at: float
    source: str = ""


TransitionSink = Callable[[Transition], None]
# Observes every advance's verdict (for metrics: retries from OPENED, verification failures from a
# resolution whose execution failed) — things transitions alone do not carry.
AdvanceSink = Callable[[str, "LifecycleOutcome"], None]

# The legal problem-state moves (rule 2). An event resolves against current state + these rules; a
# move not listed here is ignored, so an out-of-order or stale signal never corrupts the state. A
# closed problem also leaves the live map entirely, so its late events find nothing to advance.
_LEGAL: dict[ProblemState | None, frozenset[ProblemState]] = {
    None: frozenset({ProblemState.NEW, ProblemState.VERIFIED}),
    ProblemState.NEW: frozenset(
        {ProblemState.IN_PROGRESS, ProblemState.VERIFIED, ProblemState.ESCALATED}
    ),
    ProblemState.IN_PROGRESS: frozenset(
        {ProblemState.VERIFIED, ProblemState.ESCALATED}
    ),
    ProblemState.VERIFIED: frozenset({ProblemState.CLOSED}),
    ProblemState.ESCALATED: frozenset({ProblemState.IN_PROGRESS, ProblemState.VERIFIED}),
    ProblemState.CLOSED: frozenset(),
}


@dataclass(frozen=True)
class ProblemRecord:
    """A persisted problem — its signal, lifecycle state, and timestamps — enough to rebuild
    coordinator state on startup (recoverability). Disk serialization is wiring (S4b-2b-2); this is
    the in-memory ``export``/``recover`` unit."""

    signal: ProblemSignal
    state: ProblemState
    first_seen: float
    last_seen: float


class ProcessedEventLog:
    """Remembers processed event ids so a re-delivered event is ignored (rule 2). In-memory now,
    durable later; bounded by insertion order so a 24/7 service does not grow without limit."""

    def __init__(self, *, capacity: int = 10_000) -> None:
        self._seen: dict[str, None] = {}
        self._capacity = max(1, capacity)

    def seen(self, event_id: str) -> bool:
        return event_id in self._seen

    def record(self, event_id: str) -> None:
        self._seen[event_id] = None
        while len(self._seen) > self._capacity:
            self._seen.pop(next(iter(self._seen)))


class ResolutionResolver:
    """Compose strategy selection with the resolution-check plugin: pick the strategy for a
    problem, then its check, then resolve. No strategy or check → pending (needs a human)."""

    def __init__(self, strategies: StrategyRegistry, checks: ResolutionCheckRegistry) -> None:
        self._strategies = strategies
        self._checks = checks

    def resolve(self, signal: ProblemSignal) -> Resolution:
        strategy = self._strategies.select(signal)
        if strategy is None:
            return Resolution.pending("no strategy applies")
        check = self._checks.for_strategy(strategy.id)
        if check is None:
            return Resolution.pending(f"no resolution check for {strategy.id}")
        return check.resolve(signal)


_EVENT_NOTES: dict[LifecycleEventKind, str] = {
    LifecycleEventKind.APPROVAL_GRANTED: "approval granted",
    LifecycleEventKind.APPROVAL_REJECTED: "approval rejected",
    LifecycleEventKind.EXECUTION_FINISHED: "execution finished",
    LifecycleEventKind.EVIDENCE_CHANGED: "evidence changed",
    LifecycleEventKind.RUNTIME_RECOVERED: "runtime recovered",
}


class LifecycleCoordinator:
    """Advances problems through the driver, records their state transitions with reasons, and is
    the one seam both the tick and events flow through. Pure over injected collaborators (driver,
    ledger, resolver); the real evidence sources and daemon wiring are S4b-2."""

    def __init__(
        self,
        driver: LifecycleDriver,
        ledger: ProblemLedger,
        resolver: ResolutionResolver,
        *,
        on_transition: TransitionSink | None = None,
        on_advance: AdvanceSink | None = None,
        processed: ProcessedEventLog | None = None,
        attempt_reset: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._driver = driver
        self._ledger = ledger
        self._resolver = resolver
        self._on_transition = on_transition
        self._on_advance = on_advance
        self._processed = processed if processed is not None else ProcessedEventLog()
        self._attempt_reset = attempt_reset if attempt_reset is not None else (lambda _ref: None)
        self._clock = clock
        self._state: dict[str, ProblemState] = {}

    def observe(
        self, signal: ProblemSignal, *, trigger: Trigger = Trigger.CONNECTOR, source: str = ""
    ) -> bool:
        """Register or refresh a problem; a newly-detected one enters at NEW with a reason."""
        is_new = self._ledger.observe(signal)
        if is_new:
            self._to(
                signal.correlation_ref,
                ProblemState.NEW,
                f"detected: {signal.evidence_signature}",
                trigger,
                source,
            )
        return is_new

    def advance(
        self, problem: ActiveProblem, trigger: Trigger, *, note: str = "", source: str = ""
    ) -> LifecycleOutcome:
        """The single entry point (rule 1). Advance one problem through the driver and fold the
        verdict into its recorded state. ``note`` is a generic reason hint from an event (e.g.
        'approval granted'); ``source`` is the concrete emitter (rule 4)."""
        outcome = self._driver.advance(self._to_problem(problem.signal))
        self._apply(problem.correlation_ref, outcome, trigger, note, source)
        if self._on_advance is not None:
            self._on_advance(problem.correlation_ref, outcome)
        return outcome

    def tick(self) -> list[LifecycleOutcome]:
        """Reconciliation (rule 3): re-evaluate every active problem from evidence, independent of
        events. Even if every webhook is lost, the tick re-discovers the change (eventually
        consistent)."""
        return [
            self.advance(problem, Trigger.POLL, source="reconciliation")
            for problem in self._ledger.active()
        ]

    def notify(self, event: LifecycleEvent) -> LifecycleOutcome | None:
        """Advance the problem an event targets — idempotent (rule 2) and generic (rule 3). Returns
        None when the event is a duplicate or targets an unknown/closed problem (so a late event
        after close is safely ignored)."""
        if self._processed.seen(event.event_id):
            return None
        self._processed.record(event.event_id)
        problem = self._ledger.find_active(event.correlation_ref)
        if problem is None:
            return None
        note = _EVENT_NOTES.get(event.kind, "")
        return self.advance(problem, event.trigger, note=note, source=event.source)

    def state(self, correlation_ref: str) -> ProblemState | None:
        return self._state.get(correlation_ref)

    def states(self) -> dict[str, ProblemState]:
        return dict(self._state)

    def export(self) -> list[ProblemRecord]:
        """Snapshot the active problems + their states for persistence (recoverability)."""
        records: list[ProblemRecord] = []
        for problem in self._ledger.active():
            state = self._state.get(problem.correlation_ref)
            if state is not None:
                records.append(
                    ProblemRecord(problem.signal, state, problem.first_seen, problem.last_seen)
                )
        return records

    def recover(self, records: Iterable[ProblemRecord]) -> None:
        """Rebuild coordinator state from persisted records on startup — the lifecycle continues an
        in-flight problem instead of restarting from zero. No transitions are emitted: recovery
        restores the prior state, it does not re-walk it."""
        for record in records:
            self._ledger.restore(
                record.signal, first_seen=record.first_seen, last_seen=record.last_seen
            )
            self._state[record.signal.correlation_ref] = record.state

    # --- internals ---

    def _to_problem(self, signal: ProblemSignal) -> Problem:
        return Problem(
            correlation_ref=signal.correlation_ref,
            verify=lambda: self._resolver.resolve(signal),
            goal=signal.goal,
            summary=signal.summary,
            critical=signal.critical,
        )

    def _apply(
        self, ref: str, outcome: LifecycleOutcome, trigger: Trigger, note: str, source: str
    ) -> None:
        status = outcome.status
        if status is LifecycleStatus.RESOLVED:
            detail = outcome.resolution.detail if outcome.resolution is not None else ""
            self._to(ref, ProblemState.VERIFIED, detail or "resolution confirmed", trigger, source)
            self._to(ref, ProblemState.CLOSED, "resolution policy satisfied", trigger, source)
            self._ledger.deactivate(ref)
            self._reset(ref)
        elif status is LifecycleStatus.OPENED:
            number = outcome.attempt.attempt_number if outcome.attempt is not None else 0
            reason = note or f"remediation attempt {number} opened"
            self._to(ref, ProblemState.IN_PROGRESS, reason, trigger, source)
        elif status is LifecycleStatus.REMEDIATING:
            reason = note or "remediation in progress"
            self._to(ref, ProblemState.IN_PROGRESS, reason, trigger, source)
        elif status is LifecycleStatus.ESCALATED:
            tier = outcome.tier.value if outcome.tier is not None else "supervisor"
            reason = f"escalated to {tier} after attempt cap"
            self._to(ref, ProblemState.ESCALATED, reason, trigger, source)
        # PENDING → no state change (nothing to record)

    def _to(
        self, ref: str, to_state: ProblemState, reason: str, trigger: Trigger, source: str
    ) -> None:
        current = self._state.get(ref)
        if current is to_state:
            return  # no change → no transition
        if to_state not in _LEGAL.get(current, frozenset()):
            return  # out-of-order / stale → ignore, never corrupt the state (rule 2)
        self._transition(ref, current, to_state, reason, trigger, source)

    def _transition(
        self,
        ref: str,
        from_state: ProblemState | None,
        to_state: ProblemState,
        reason: str,
        trigger: Trigger,
        source: str,
    ) -> None:
        self._state[ref] = to_state
        if self._on_transition is not None:
            at = self._clock()
            self._on_transition(
                Transition(ref, from_state, to_state, reason, trigger, at, source)
            )

    def _reset(self, ref: str) -> None:
        # A closed problem leaves the live state map (its history is in the transition log); a
        # recurrence starts a fresh lineage. The attempt store is reset via the injected seam.
        self._state.pop(ref, None)
        self._attempt_reset(ref)
