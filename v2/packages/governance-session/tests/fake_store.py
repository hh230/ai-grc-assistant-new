"""An in-memory `GovernanceStorePort` test double — no database. Mirrors
`PostgresGovernanceStore`'s method surface exactly (tenant-scoped reads/writes, append-only
answers) so the service's tests exercise real orchestration logic without Postgres."""

from __future__ import annotations

from dataclasses import dataclass

from governance_discovery.session import DiscoverySession
from governance_discovery.signal import SignalSet


@dataclass
class _AnswerRow:
    question_id: str
    sequence: int
    raw_answer: object
    resolved_signal_key: str | None


class FakeGovernanceStore:
    def __init__(self) -> None:
        self._sessions: dict[str, DiscoverySession] = {}
        self._answers: dict[str, list[_AnswerRow]] = {}
        self.organization_baselines: dict[str, tuple[tuple[str, ...], SignalSet]] = {}

    def save_session(self, session: DiscoverySession) -> None:
        self._sessions[session.id] = session

    def get_session(self, session_id: str, tenant_id: str) -> DiscoverySession | None:
        session = self._sessions.get(session_id)
        return session if session is not None and session.tenant_id == tenant_id else None

    def find_in_progress_session(self, tenant_id: str) -> DiscoverySession | None:
        candidates = [
            s for s in self._sessions.values() if s.tenant_id == tenant_id and s.status == "in_progress"
        ]
        return max(candidates, key=lambda s: s.updated_at, default=None)

    def next_sequence(self, session_id: str) -> int:
        rows = self._answers.get(session_id, [])
        return (max((r.sequence for r in rows), default=0)) + 1

    def append_answer(self, **fields: object) -> None:
        row = _AnswerRow(
            question_id=fields["question_id"],
            sequence=fields["sequence"],
            raw_answer=fields["raw_answer"],
            resolved_signal_key=fields["resolved_signal_key"],
        )
        self._answers.setdefault(fields["session_id"], []).append(row)

    def answer_history(self, session_id: str, tenant_id: str) -> list[_AnswerRow]:
        return sorted(self._answers.get(session_id, []), key=lambda r: r.sequence)

    def upsert_organization_baseline(
        self, tenant_id: str, active_packs: tuple[str, ...], signals: SignalSet, now: float
    ) -> None:
        self.organization_baselines[tenant_id] = (active_packs, signals)
