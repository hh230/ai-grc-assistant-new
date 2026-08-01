"""The correlated fix-it chain model — attempt tracking for continue-until-green (ADR 0061).

A devteam-layer concept ONLY: the Core Mission, the Mission Engine, and the correlation model are
untouched. Each fix-it mission in a chain is recorded as a ChainAttempt (its ``correlation_ref`` + a
1-based ``attempt_number`` + the ``mission_id`` it opened). The AttemptStore keeps the full chain
history per ref and is the SINGLE SOURCE OF TRUTH — the Driver reads the latest attempt (and, via
its mission_id, that mission's live status) from the store, holding no state itself. This module is
the DATA + STATE only; the Driver owns the policy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChainAttempt:
    """One attempt in a correlated fix-it chain — the durable record of a fix-it mission the chain
    opened. It carries the ``mission_id`` so the AttemptStore stays the SINGLE SOURCE OF TRUTH: the
    Driver reads the latest attempt's mission status from the store and keeps NO in-memory state, so
    a Worker restart cannot lose track of an in-flight attempt. 1-based ``attempt_number``."""

    correlation_ref: str
    attempt_number: int = 1
    mission_id: str = ""

    @property
    def is_first(self) -> bool:
        return self.attempt_number == 1

    @property
    def label(self) -> str:
        """A human-readable tag for the mission goal / audit (how a mission 'carries' its place)."""
        return f"attempt {self.attempt_number}"


@dataclass(frozen=True)
class ChainAlert:
    """Raised when a chain exhausts max_attempts: the issue needs human intervention, not another
    automated attempt — what the Driver emits INSTEAD of opening a new mission past the cap."""

    correlation_ref: str
    attempts: int
    reason: str


class AttemptStore:
    """The full chain history per correlation_ref — every ChainAttempt, not just the last, so the
    Driver can show the chain, count attempts, and put the history in an alert or audit. A
    devteam-layer concern — the correlation model is untouched; in-memory now, durable later. PURE
    storage: stores, and returns history / latest / count. All policy stays in the Driver."""

    def __init__(self) -> None:
        self._history: dict[str, list[ChainAttempt]] = {}

    def record(self, attempt: ChainAttempt) -> None:
        self._history.setdefault(attempt.correlation_ref, []).append(attempt)

    def history(self, correlation_ref: str) -> tuple[ChainAttempt, ...]:
        return tuple(self._history.get(correlation_ref, ()))

    def latest(self, correlation_ref: str) -> ChainAttempt | None:
        attempts = self._history.get(correlation_ref)
        return attempts[-1] if attempts else None

    def count(self, correlation_ref: str) -> int:
        return len(self._history.get(correlation_ref, ()))

    def forget(self, correlation_ref: str) -> None:
        """Drop a chain's history — e.g. after the problem is resolved, so a recurrence starts a
        fresh lineage rather than inheriting a spent attempt count. Idempotent."""
        self._history.pop(correlation_ref, None)
