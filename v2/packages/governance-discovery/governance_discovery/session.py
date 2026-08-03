"""`DiscoverySession` — the persisted aggregate a `discovery_sessions` row round-trips (ADR 0066
§2). Pure data: no clock, no I/O, no database. Timestamps are always caller-supplied (matching the
Mission aggregate's convention) so the aggregate stays deterministic and unit-testable — the
orchestration that actually calls `time.time()` and drives transitions lives one layer up, in the
`governance-session` service package.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from governance_discovery.analysis import Applicability
from governance_discovery.engine import DiscoverySessionState
from governance_discovery.signal import SignalSet

SessionStatus = Literal["in_progress", "concluded", "abandoned"]


@dataclass(frozen=True)
class DiscoverySession:
    id: str
    tenant_id: str
    status: SessionStatus
    signals: SignalSet
    answered_question_ids: frozenset[str]
    active_pack_ids: tuple[str, ...]
    pack_versions: dict[str, str]
    confidence_score: float
    applicability: Applicability | None
    created_at: float
    updated_at: float
    concluded_at: float | None = None
    # An audit/display convenience only — the question actually presented next is ALWAYS
    # recomputed live via `DiscoveryEngine.next_question(session.state)`, never trusted from here.
    current_question_id: str | None = None

    @property
    def state(self) -> DiscoverySessionState:
        """The view `DiscoveryEngine` (Tier A) operates on."""
        return DiscoverySessionState(
            signals=self.signals, answered_question_ids=self.answered_question_ids
        )

    @classmethod
    def start(cls, session_id: str, tenant_id: str, now: float) -> DiscoverySession:
        return cls(
            id=session_id,
            tenant_id=tenant_id,
            status="in_progress",
            signals=SignalSet(),
            answered_question_ids=frozenset(),
            active_pack_ids=(),
            pack_versions={},
            confidence_score=0.0,
            applicability=None,
            created_at=now,
            updated_at=now,
        )

    def with_answer(
        self,
        *,
        question_id: str,
        signal_key: str,
        signal,  # governance_discovery.signal.Signal — avoids a circular import hint
        active_pack_ids: tuple[str, ...],
        pack_versions: dict[str, str],
        now: float,
    ) -> DiscoverySession:
        return replace(
            self,
            signals=self.signals.with_signal(signal),
            answered_question_ids=self.answered_question_ids | {question_id},
            active_pack_ids=active_pack_ids,
            pack_versions={**self.pack_versions, **pack_versions},
            updated_at=now,
        )

    def with_answered_only(self, *, question_id: str, now: float) -> DiscoverySession:
        """Marks a question answered WITHOUT writing a signal — the 'skip' path for an optional
        question (free-text clarifications, supplementary multi-select context). Active packs are
        unchanged since no signal changed."""
        return replace(
            self, answered_question_ids=self.answered_question_ids | {question_id}, updated_at=now
        )

    def concluded(self, applicability: Applicability, now: float) -> DiscoverySession:
        return replace(
            self,
            status="concluded",
            applicability=applicability,
            confidence_score=applicability.confidence_score,
            current_question_id=None,
            updated_at=now,
            concluded_at=now,
        )

    def presenting(self, question_id: str | None, now: float) -> DiscoverySession:
        """Record which question was just computed and shown — audit/display only (see the field
        docstring above)."""
        return replace(self, current_question_id=question_id, updated_at=now)
