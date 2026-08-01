"""Problem correlation — one detected condition, one durable lineage (ADR 0065, ADR-0064 pattern).

A ``ProblemSignal`` is a **domain-agnostic** detection: WHAT kind of mission it needs
(``mission_type``), WHICH thing it concerns (``asset``), and the fingerprint of the evidence
(``evidence_signature``). Its identity —
``correlation_ref = {mission_type}:{asset}:{evidence_signature}`` (owner principle, 2026-07-30) —
tracks a problem correctly across ALL domains: the same condition on different assets is a different
lineage, the same condition recurring on one asset dedups, and domains never collide (a compliance
gap on a control ≠ a TLS issue on a host).

The ``ProblemLedger`` is the org's active-problem set (the ADR-0064 pattern, org-local): observe a
signal to register or refresh a problem, list the active problems the lifecycle drives, and
deactivate one on **verified resolution** so a later recurrence is a NEW problem, not a revival.
The org runs under one tenant (``tenant:platform``), so the ledger is single-tenant; a tenant
dimension can be added if the organization ever serves several.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from devteam_protocol import AgentCapability


class Severity(str, Enum):
    """How serious a problem is — scales the approval a remediation needs and escalation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def _clean(part: str) -> str:
    """A key part with the ':' separator and surrounding space removed, so ``mission_type`` and
    ``asset`` can never split the correlation key ambiguously."""
    return part.strip().replace(":", "_")


@dataclass(frozen=True)
class ProblemSignal:
    """A detected condition that seeds/correlates a mission. Domain-agnostic: ``mission_type`` names
    the kind of work (``tls_remediation``, ``compliance_gap``, …), ``asset`` the subject (a host, a
    control, a policy, a service), ``evidence_signature`` the fingerprint of the specific evidence.
    ``goal`` / ``summary`` describe the mission; ``stages`` scope it; ``critical`` → CEO."""

    mission_type: str
    asset: str
    evidence_signature: str
    goal: str = ""
    summary: str = ""
    stages: tuple[AgentCapability, ...] = ()
    severity: Severity = Severity.MEDIUM
    connector_id: str = ""  # provenance (not identity): the connector to re-fetch when verifying

    @property
    def critical(self) -> bool:
        """Critical problems route escalation straight to the CEO (the driver's ``critical``)."""
        return self.severity is Severity.CRITICAL

    @property
    def correlation_ref(self) -> str:
        """The identity ``{mission_type}:{asset}:{evidence_signature}`` (ADR 0065 decision 2).
        Type and asset are sanitized colon-free; the free-form evidence is the tail."""
        return f"{_clean(self.mission_type)}:{_clean(self.asset)}:{self.evidence_signature}"


@dataclass
class ActiveProblem:
    """A live problem in the ledger: its latest signal plus when it was first and last observed."""

    signal: ProblemSignal
    first_seen: float
    last_seen: float

    @property
    def correlation_ref(self) -> str:
        return self.signal.correlation_ref


class ProblemLedger:
    """The active-problem set — ADR-0064's register / find_active / deactivate, org-local.
    ``observe`` registers a new problem or refreshes an existing one; ``active`` is what the
    lifecycle drives; ``deactivate`` closes one on resolution. PURE storage; policy in driver."""

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._active: dict[str, ActiveProblem] = {}
        self._clock = clock

    def observe(self, signal: ProblemSignal) -> bool:
        """Register the problem if new (True) or refresh the existing one (False). A fresh signal
        for an active ref is NOT a new problem — the lifecycle already handles it (dedup)."""
        ref = signal.correlation_ref
        now = self._clock()
        existing = self._active.get(ref)
        if existing is None:
            self._active[ref] = ActiveProblem(signal=signal, first_seen=now, last_seen=now)
            return True
        existing.signal = signal
        existing.last_seen = now
        return False

    def is_active(self, correlation_ref: str) -> bool:
        return correlation_ref in self._active

    def find_active(self, correlation_ref: str) -> ActiveProblem | None:
        return self._active.get(correlation_ref)

    def active(self) -> tuple[ActiveProblem, ...]:
        """Every active problem, oldest first — the set the lifecycle advances each tick."""
        return tuple(sorted(self._active.values(), key=lambda problem: problem.first_seen))

    def deactivate(self, correlation_ref: str) -> bool:
        """Close a problem on verified resolution; a later recurrence registers a fresh lineage.
        Returns whether it was active."""
        return self._active.pop(correlation_ref, None) is not None

    def restore(self, signal: ProblemSignal, *, first_seen: float, last_seen: float) -> None:
        """Re-register a persisted problem on startup, preserving its timestamps — the ledger is the
        durable source the coordinator recovers from, not just memory (recoverability)."""
        self._active[signal.correlation_ref] = ActiveProblem(
            signal=signal, first_seen=first_seen, last_seen=last_seen
        )
