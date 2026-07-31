"""Lifecycle metrics — make the organization measurable, not just operable (ADR 0065, owner rule).

Beyond the audit trail, the lifecycle emits metrics: how many problems are active, how long they
take to verify and close, how often remediations retry or escalate, how often verification fails,
and how fast events are processed. Wired as the coordinator's ``on_transition`` + ``on_advance``
observers plus ``record_event`` for the event path — nothing in the coordinator's logic changes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from devteam_organization.lifecycle.coordinator import ProblemState, Transition
from devteam_organization.lifecycle.driver import LifecycleOutcome, LifecycleStatus


@dataclass(frozen=True)
class LifecycleMetricsSnapshot:
    """A point-in-time reading of the lifecycle's health."""

    active_problems: int
    mean_time_to_verify: float | None  # NEW → VERIFIED, seconds
    mean_time_to_close: float | None  # NEW → CLOSED, seconds
    retry_count: int  # remediation attempts opened beyond the first
    escalation_count: int
    verification_failures: int  # a remediation ran but did not resolve (execution_failed)
    events_processed: int
    mean_event_latency_ms: float | None
    # MTTD (occurrence → detection) needs the evidence's real occurrence time, which the connectors
    # do not yet carry; it is surfaced once they do (S4b-2b-2). Until then it stays None.
    mean_time_to_detect: float | None = None


class LifecycleMetrics:
    """Accumulates lifecycle metrics from the coordinator's streams. Pure; the daemon publishes the
    snapshot to the journal/dashboard (wiring)."""

    def __init__(self) -> None:
        # ``_open_at`` holds every open problem's detection time (NEW → CLOSED). Its length IS the
        # live active count, so it always agrees with the ledger; restoring it recovers both the
        # active count and the mean-time durations across a daemon restart.
        self._open_at: dict[str, float] = {}
        self._verify_durations: list[float] = []
        self._close_durations: list[float] = []
        self._retries = 0
        self._escalations = 0
        self._verification_failures = 0
        self._events = 0
        self._event_latency_ms = 0.0

    def record_transition(self, transition: Transition) -> None:
        ref, at = transition.correlation_ref, transition.at
        if transition.to_state is ProblemState.NEW:
            self._open_at[ref] = at
        elif transition.to_state is ProblemState.VERIFIED:
            started = self._open_at.get(ref)
            if started is not None:
                self._verify_durations.append(at - started)
        elif transition.to_state is ProblemState.CLOSED:
            started = self._open_at.pop(ref, None)
            if started is not None:
                self._close_durations.append(at - started)
        elif transition.to_state is ProblemState.ESCALATED:
            self._escalations += 1

    def record_advance(self, _ref: str, outcome: LifecycleOutcome) -> None:
        opened_retry = (
            outcome.status is LifecycleStatus.OPENED
            and outcome.attempt is not None
            and outcome.attempt.attempt_number > 1
        )
        if opened_retry:
            self._retries += 1
        if outcome.resolution is not None and outcome.resolution.execution_verified is False:
            self._verification_failures += 1

    def record_event(self, latency_ms: float) -> None:
        self._events += 1
        self._event_latency_ms += max(0.0, latency_ms)

    def snapshot(self) -> LifecycleMetricsSnapshot:
        latency = self._event_latency_ms / self._events if self._events else None
        return LifecycleMetricsSnapshot(
            active_problems=len(self._open_at),  # the live count — always agrees with the ledger
            mean_time_to_verify=_mean(self._verify_durations),
            mean_time_to_close=_mean(self._close_durations),
            retry_count=self._retries,
            escalation_count=self._escalations,
            verification_failures=self._verification_failures,
            events_processed=self._events,
            mean_event_latency_ms=latency,
        )

    def export(self) -> dict[str, object]:
        """The internals needed to resume metrics after a restart (open times + accumulators)."""
        return {
            "open_at": dict(self._open_at),
            "verify_durations": list(self._verify_durations),
            "close_durations": list(self._close_durations),
            "retries": self._retries,
            "escalations": self._escalations,
            "verification_failures": self._verification_failures,
        }

    def restore(self, data: Mapping[str, object]) -> None:
        """Resume from an ``export`` (recoverability): active + mean-times survive a restart."""
        items = _mapping(data.get("open_at")).items()
        self._open_at = {k: float(v) for k, v in items if isinstance(v, (int, float))}
        self._verify_durations = _float_list(data.get("verify_durations"))
        self._close_durations = _float_list(data.get("close_durations"))
        self._retries = _int(data.get("retries"))
        self._escalations = _int(data.get("escalations"))
        self._verification_failures = _int(data.get("verification_failures"))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _float_list(value: object) -> list[float]:
    if not isinstance(value, list):
        return []
    return [float(v) for v in value if isinstance(v, (int, float))]


def _int(value: object) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0
