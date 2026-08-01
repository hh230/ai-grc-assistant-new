"""The Mission Lifecycle core (ADR 0065) — pure policy: verification + the escalation ladder.

These lock the two owner-set rules: closure requires the originating evidence to be gone AND (where
a remediation ran) execution proven — a failed execution never closes; and escalation climbs a
two-tier Supervisor → CEO ladder (critical goes straight to CEO; persistence promotes past grace).
"""

from __future__ import annotations

from devteam_chain import AttemptStore, ChainAlert, ChainAttempt
from devteam_organization.lifecycle import (
    EscalationLedger,
    EscalationTier,
    LifecycleDriver,
    LifecycleStatus,
    Problem,
    Resolution,
)


class _Clock:
    """A hand-cranked clock so grace-period timing is deterministic."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _problem(
    verify_result: Resolution, *, critical: bool = False, ref: str = "org:tls:host"
) -> Problem:
    return Problem(
        correlation_ref=ref,
        verify=lambda: verify_result,
        goal="renew the cert",
        summary="TLS expiring",
        critical=critical,
    )


def _driver(
    store: AttemptStore,
    *,
    opened: list[str] | None = None,
    finished: bool = True,
    escalations: EscalationLedger | None = None,
    clock: _Clock | None = None,
    max_attempts: int = 3,
    ceo_grace_seconds: float = 3600.0,
) -> tuple[LifecycleDriver, list[tuple[str, int]], list[tuple[EscalationTier, ChainAlert]]]:
    """A driver plus recorders: the (ref, number) opens and the (tier, alert) escalations."""
    ids = iter(opened if opened is not None else ["m1", "m2", "m3", "m4"])
    open_calls: list[tuple[str, int]] = []
    escalated: list[tuple[EscalationTier, ChainAlert]] = []

    def open_remediation(problem: Problem, number: int) -> str | None:
        open_calls.append((problem.correlation_ref, number))
        return next(ids, None)

    def raise_escalation(problem: Problem, tier: EscalationTier, alert: ChainAlert) -> None:
        escalated.append((tier, alert))

    driver = LifecycleDriver(
        store,
        open_remediation=open_remediation,
        raise_escalation=raise_escalation,
        is_finished=lambda _attempt: finished,
        escalations=escalations,
        max_attempts=max_attempts,
        ceo_grace_seconds=ceo_grace_seconds,
        clock=clock if clock is not None else _Clock(),
    )
    return driver, open_calls, escalated


# --- the verification contract (evidence-cleared + execution-evidence) ---


def test_resolution_truth_table() -> None:
    assert Resolution.pending().resolved is False
    assert Resolution.cleared().resolved is True  # evidence gone, execution N/A (human-ops)
    assert Resolution.confirmed().resolved is True  # evidence gone + execution proven
    # The owner's guard: a remediation that ran but did NOT succeed never closes the problem, even
    # though the symptom (evidence_cleared) transiently reads clear.
    assert Resolution.execution_failed().resolved is False
    assert Resolution(evidence_cleared=False, execution_verified=True).resolved is False


def test_resolved_closes_and_clears_escalations() -> None:
    store = AttemptStore()
    ledger = EscalationLedger()
    ledger.record("org:tls:host", EscalationTier.SUPERVISOR, at=1.0)
    driver, opens, escalated = _driver(store, escalations=ledger)

    outcome = driver.advance(_problem(Resolution.confirmed()))

    assert outcome.status is LifecycleStatus.RESOLVED
    assert opens == [] and escalated == []
    assert ledger.raised("org:tls:host") == frozenset()  # ladder reset for a fresh recurrence


def test_execution_failed_does_not_close_and_opens_an_attempt() -> None:
    store = AttemptStore()
    driver, opens, _ = _driver(store)

    outcome = driver.advance(_problem(Resolution.execution_failed()))

    assert outcome.status is LifecycleStatus.OPENED  # NOT resolved → the lifecycle keeps working it
    assert opens == [("org:tls:host", 1)]


# --- attempt lineage (open / wait / next) ---


def test_opens_first_attempt_when_unresolved_and_empty() -> None:
    store = AttemptStore()
    driver, opens, _ = _driver(store, opened=["mission-1"])

    outcome = driver.advance(_problem(Resolution.pending()))

    assert outcome.status is LifecycleStatus.OPENED
    assert outcome.mission_id == "mission-1"
    assert opens == [("org:tls:host", 1)]
    assert store.count("org:tls:host") == 1
    assert store.latest("org:tls:host") == ChainAttempt("org:tls:host", 1, mission_id="mission-1")


def test_waits_while_the_attempt_is_in_flight() -> None:
    store = AttemptStore()
    store.record(ChainAttempt("org:tls:host", 1, mission_id="m1"))
    driver, opens, _ = _driver(store, finished=False)  # the in-flight mission is not terminal

    outcome = driver.advance(_problem(Resolution.pending()))

    assert outcome.status is LifecycleStatus.REMEDIATING
    assert opens == []  # no second attempt while one is in flight
    assert store.count("org:tls:host") == 1


def test_opens_next_attempt_once_the_previous_finished() -> None:
    store = AttemptStore()
    store.record(ChainAttempt("org:tls:host", 1, mission_id="m1"))
    driver, opens, _ = _driver(store, opened=["m2"], finished=True)

    outcome = driver.advance(_problem(Resolution.pending()))

    assert outcome.status is LifecycleStatus.OPENED
    assert opens == [("org:tls:host", 2)]
    assert store.count("org:tls:host") == 2


def test_open_returning_none_is_pending() -> None:
    store = AttemptStore()
    driver, opens, _ = _driver(store, opened=[])  # nothing to open this pass

    outcome = driver.advance(_problem(Resolution.pending()))

    assert outcome.status is LifecycleStatus.PENDING
    assert opens == [("org:tls:host", 1)]
    assert store.count("org:tls:host") == 0  # no attempt recorded when nothing opened


# --- the two-tier escalation ladder ---


def _exhausted_store(ref: str = "org:tls:host") -> AttemptStore:
    store = AttemptStore()
    for n in (1, 2, 3):
        store.record(ChainAttempt(ref, n, mission_id=f"m{n}"))
    return store


def test_escalates_to_supervisor_at_the_cap() -> None:
    store = _exhausted_store()
    ledger = EscalationLedger()
    driver, opens, escalated = _driver(store, escalations=ledger, clock=_Clock(5000.0))

    outcome = driver.advance(_problem(Resolution.pending()))

    assert outcome.status is LifecycleStatus.ESCALATED
    assert outcome.tier is EscalationTier.SUPERVISOR
    assert opens == []  # no more automated attempts past the cap
    assert [tier for tier, _ in escalated] == [EscalationTier.SUPERVISOR]
    assert outcome.alert is not None and outcome.alert.attempts == 3
    assert ledger.raised("org:tls:host") == frozenset({EscalationTier.SUPERVISOR})


def test_supervisor_then_pending_within_grace() -> None:
    store = _exhausted_store()
    ledger = EscalationLedger()
    ledger.record("org:tls:host", EscalationTier.SUPERVISOR, at=1000.0)
    clock = _Clock(1000.0 + 60.0)  # only a minute after the supervisor escalation
    driver, _, escalated = _driver(store, escalations=ledger, clock=clock, ceo_grace_seconds=3600.0)

    outcome = driver.advance(_problem(Resolution.pending()))

    assert outcome.status is LifecycleStatus.PENDING  # grace not elapsed, not critical → hold
    assert escalated == []


def test_supervisor_then_ceo_after_grace() -> None:
    store = _exhausted_store()
    ledger = EscalationLedger()
    ledger.record("org:tls:host", EscalationTier.SUPERVISOR, at=1000.0)
    clock = _Clock(1000.0 + 3600.0)  # the grace has elapsed
    driver, _, escalated = _driver(store, escalations=ledger, clock=clock, ceo_grace_seconds=3600.0)

    outcome = driver.advance(_problem(Resolution.pending()))

    assert outcome.status is LifecycleStatus.ESCALATED
    assert outcome.tier is EscalationTier.CEO
    assert [tier for tier, _ in escalated] == [EscalationTier.CEO]
    assert ledger.raised("org:tls:host") == frozenset(
        {EscalationTier.SUPERVISOR, EscalationTier.CEO}
    )


def test_critical_escalates_straight_to_ceo() -> None:
    store = _exhausted_store()
    ledger = EscalationLedger()
    driver, _, escalated = _driver(store, escalations=ledger)

    outcome = driver.advance(_problem(Resolution.pending(), critical=True))

    assert outcome.status is LifecycleStatus.ESCALATED
    assert outcome.tier is EscalationTier.CEO  # critical skips the Supervisor tier
    assert [tier for tier, _ in escalated] == [EscalationTier.CEO]
    assert EscalationTier.SUPERVISOR not in ledger.raised("org:tls:host")


def test_ceo_already_raised_is_pending() -> None:
    store = _exhausted_store()
    ledger = EscalationLedger()
    ledger.record("org:tls:host", EscalationTier.SUPERVISOR, at=1000.0)
    ledger.record("org:tls:host", EscalationTier.CEO, at=2000.0)
    driver, _, escalated = _driver(store, escalations=ledger, clock=_Clock(9000.0))

    outcome = driver.advance(_problem(Resolution.pending()))

    assert outcome.status is LifecycleStatus.PENDING  # top tier reached; a human owns it now
    assert escalated == []


def test_cleared_evidence_without_execution_closes_a_human_ops_problem() -> None:
    store = _exhausted_store()  # even past the cap, a genuine clear closes it
    driver, _, escalated = _driver(store)

    outcome = driver.advance(_problem(Resolution.cleared("symptom gone")))

    assert outcome.status is LifecycleStatus.RESOLVED
    assert escalated == []
