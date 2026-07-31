"""The Mission Lifecycle core — drive a detected problem to closure (ADR 0065).

Pure policy over injected seams, mirroring the engineering squad's ``ChainDriver`` (ADR 0061):
given a ``Problem`` — a durable ``correlation_ref``, how to *verify* it, and (via seams) how to
*remediate* and *escalate* it — ``advance()`` decides whether the problem is **RESOLVED**,
a remediation is still in flight, the next attempt should **open**, or it must **escalate**. The
Driver holds no state: attempt lineage lives in the reused ``AttemptStore`` and escalation state in
an injected ``EscalationLedger``. This module is DATA + POLICY only — connectors, the runtime, and
the tick are wired elsewhere, so the core imports nothing from the Mission Engine.

Two owner-set rules (ADR 0065) shape it:

- **Verification is evidence-cleared AND execution-evidence.** A problem closes only when the
  evidence that created it is gone (a fresh, successful re-observation without the originating
  signature) *and*, where a remediation executed, that remediation's own success is proven.
  "Execution finished" alone never closes — a remediation that ran but failed
  (``execution_verified is False``) keeps the problem open even if the symptom transiently cleared.
- **Escalation is a two-tier ladder.** At the attempt cap, escalate to the **Supervisor**; if the
  problem is **critical** or **persists past a grace period**, escalate to the **CEO**.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from devteam_chain import AttemptStore, ChainAlert, ChainAttempt


class LifecycleStatus(str, Enum):
    """The verdict of one ``LifecycleDriver.advance``."""

    RESOLVED = "resolved"  # evidence gone + execution proven → closed
    REMEDIATING = "remediating"  # an attempt is in flight (mission not terminal) → wait
    OPENED = "opened"  # opened the next remediation attempt (under the cap)
    ESCALATED = "escalated"  # cap reached / critical → an escalation was raised (see ``tier``)
    PENDING = "pending"  # nothing to do this pass (nothing to open, or top tier already raised)


class EscalationTier(str, Enum):
    """Who a problem escalates to. The ladder climbs Supervisor → CEO (ADR 0065 decision 7)."""

    SUPERVISOR = "supervisor"  # first tier: automated attempts exhausted
    CEO = "ceo"  # second tier: the problem is critical, or persisted past the grace period


@dataclass(frozen=True)
class Resolution:
    """The verdict of a problem's verification. Closure (``resolved``) requires the **originating
    evidence to be gone** AND, where a remediation ran, that **execution to be proven** — never
    "execution finished" alone (ADR 0065 decision 3). ``execution_verified is None`` means no
    execution was expected (e.g. a human-ops problem verified by the symptom disappearing)."""

    evidence_cleared: bool
    execution_verified: bool | None = None
    detail: str = ""

    @property
    def resolved(self) -> bool:
        # Evidence gone AND (execution proven OR execution not applicable). A failed execution
        # (execution_verified is False) never closes, even if the symptom transiently cleared.
        return self.evidence_cleared and self.execution_verified is not False

    @classmethod
    def pending(cls, detail: str = "") -> Resolution:
        """The evidence is still present (or could not be observed) — not resolved."""
        return cls(evidence_cleared=False, detail=detail)

    @classmethod
    def cleared(cls, detail: str = "") -> Resolution:
        """Originating evidence gone; no execution proof expected (human-ops / Class B)."""
        return cls(evidence_cleared=True, execution_verified=None, detail=detail)

    @classmethod
    def confirmed(cls, detail: str = "") -> Resolution:
        """The originating evidence is gone AND the remediation's execution is proven."""
        return cls(evidence_cleared=True, execution_verified=True, detail=detail)

    @classmethod
    def execution_failed(cls, detail: str = "") -> Resolution:
        """The remediation executed but did not succeed — the problem stays open regardless."""
        return cls(evidence_cleared=True, execution_verified=False, detail=detail)


# How to re-check a problem's resolution (the two-part contract). The connector re-fetch + signature
# absence + any execution-evidence live inside this callable; the Driver stays connector-agnostic.
VerifyProblem = Callable[[], Resolution]


@dataclass(frozen=True)
class Problem:
    """A detected problem the lifecycle drives to closure. ``correlation_ref`` is the durable
    identity (one problem = one lineage). ``verify`` re-checks resolution (evidence-cleared +
    execution-evidence). ``critical`` routes escalation straight to the CEO. ``goal``/``summary``
    describe it for the remediation mission and any alert."""

    correlation_ref: str
    verify: VerifyProblem
    goal: str = ""
    summary: str = ""
    critical: bool = False


# Open the next gated remediation attempt for a problem (1-based attempt number); returns the opened
# mission id, or None when there is nothing to open this pass.
OpenRemediation = Callable[[Problem, int], "str | None"]
# Raise an escalation (open the Supervisor/CEO mission, notify) — the wiring performs it; the Driver
# builds the alert and hands it over.
RaiseEscalation = Callable[[Problem, EscalationTier, ChainAlert], None]
# Is an attempt's remediation mission terminal? (reads the mission's live status by ``mission_id``).
IsFinished = Callable[[ChainAttempt], bool]


@dataclass(frozen=True)
class LifecycleOutcome:
    """What one ``advance`` decided — the status plus whatever it produced (the resolution verdict,
    the opened attempt/mission id, or the escalation tier + alert)."""

    status: LifecycleStatus
    resolution: Resolution | None = None
    mission_id: str | None = None
    attempt: ChainAttempt | None = None
    tier: EscalationTier | None = None
    alert: ChainAlert | None = None


class EscalationLedger:
    """Which escalation tiers were raised for a problem, and when — so the ladder raises each tier
    once and can time the Supervisor→CEO grace. In-memory now, durable later (same shape as
    ``AttemptStore``). PURE storage; the Driver owns the ladder policy."""

    def __init__(self) -> None:
        self._raised: dict[str, dict[EscalationTier, float]] = {}

    def record(self, correlation_ref: str, tier: EscalationTier, *, at: float) -> None:
        self._raised.setdefault(correlation_ref, {})[tier] = at

    def raised(self, correlation_ref: str) -> frozenset[EscalationTier]:
        return frozenset(self._raised.get(correlation_ref, {}))

    def raised_at(self, correlation_ref: str, tier: EscalationTier) -> float | None:
        return self._raised.get(correlation_ref, {}).get(tier)

    def clear(self, correlation_ref: str) -> None:
        self._raised.pop(correlation_ref, None)


class LifecycleDriver:
    """Drive one problem per ``advance`` (the sibling of ``ChainDriver``). Stateless: the injected
    ``AttemptStore`` is the source of truth for attempts, the ``EscalationLedger`` for escalation.
    Inject how to open a remediation, how to raise an escalation, and whether an attempt is done."""

    def __init__(
        self,
        store: AttemptStore,
        *,
        open_remediation: OpenRemediation,
        raise_escalation: RaiseEscalation,
        is_finished: IsFinished,
        escalations: EscalationLedger | None = None,
        max_attempts: int = 3,
        ceo_grace_seconds: float = 3600.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._open = open_remediation
        self._raise = raise_escalation
        self._is_finished = is_finished
        self._escalations = escalations if escalations is not None else EscalationLedger()
        self._max_attempts = max(1, max_attempts)
        self._ceo_grace = max(0.0, ceo_grace_seconds)
        self._clock = clock

    def advance(self, problem: Problem) -> LifecycleOutcome:
        """One lifecycle pass: resolve → wait → open the next attempt → escalate."""
        ref = problem.correlation_ref
        resolution = problem.verify()
        if resolution.resolved:
            # Closed: originating evidence gone (execution proven where it ran). Reset the
            # escalation ladder so a later recurrence starts fresh; attempt lineage is reset by the
            # caller (the correlation opener).
            self._escalations.clear(ref)
            return LifecycleOutcome(LifecycleStatus.RESOLVED, resolution=resolution)

        # One attempt in flight per problem: while the latest mission is not terminal, wait.
        latest = self._store.latest(ref)
        if latest is not None and not self._is_finished(latest):
            return LifecycleOutcome(
                LifecycleStatus.REMEDIATING, resolution=resolution, attempt=latest
            )

        # Automated attempts exhausted → climb the escalation ladder instead of opening another.
        if self._store.count(ref) >= self._max_attempts:
            return self._escalate_ladder(problem, resolution)

        # Under the cap → open the next gated remediation attempt.
        number = latest.attempt_number + 1 if latest is not None else 1
        mission_id = self._open(problem, number)
        if mission_id is None:
            return LifecycleOutcome(LifecycleStatus.PENDING, resolution=resolution)
        attempt = ChainAttempt(ref, number, mission_id=mission_id)
        self._store.record(attempt)
        return LifecycleOutcome(
            LifecycleStatus.OPENED, resolution=resolution, mission_id=mission_id, attempt=attempt
        )

    def _escalate_ladder(self, problem: Problem, resolution: Resolution) -> LifecycleOutcome:
        ref = problem.correlation_ref
        raised = self._escalations.raised(ref)

        # Already at the top tier → nothing more to automate; a human owns it now.
        if EscalationTier.CEO in raised:
            return LifecycleOutcome(LifecycleStatus.PENDING, resolution=resolution)

        # The Supervisor is engaged → climb to the CEO when critical or the grace has elapsed.
        if EscalationTier.SUPERVISOR in raised:
            raised_at = self._escalations.raised_at(ref, EscalationTier.SUPERVISOR)
            if raised_at is None:
                raised_at = self._clock()
            if problem.critical or (self._clock() - raised_at) >= self._ceo_grace:
                return self._raise_tier(problem, EscalationTier.CEO, resolution)
            return LifecycleOutcome(LifecycleStatus.PENDING, resolution=resolution)

        # First time at the cap → the Supervisor, unless the problem is critical (straight to CEO).
        first = EscalationTier.CEO if problem.critical else EscalationTier.SUPERVISOR
        return self._raise_tier(problem, first, resolution)

    def _raise_tier(
        self, problem: Problem, tier: EscalationTier, resolution: Resolution
    ) -> LifecycleOutcome:
        count = self._store.count(problem.correlation_ref)
        what = problem.summary or problem.goal or problem.correlation_ref
        reason = f"{what} — escalated to {tier.value} after {count} attempt(s)"
        alert = ChainAlert(problem.correlation_ref, count, reason)
        self._raise(problem, tier, alert)
        self._escalations.record(problem.correlation_ref, tier, at=self._clock())
        return LifecycleOutcome(
            LifecycleStatus.ESCALATED, resolution=resolution, tier=tier, alert=alert
        )
