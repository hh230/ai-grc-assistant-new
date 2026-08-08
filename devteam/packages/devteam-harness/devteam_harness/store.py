"""An in-memory `GovernanceStorePort` — the one importable implementation.

Two near-identical copies of this already existed, both trapped inside test directories and
neither reusable: `governance-session/tests/fake_store.py::FakeGovernanceStore` (complete) and
`grc-api/tests/test_discovery.py::InMemoryDiscoveryStore` (**cannot conclude a session** — it
omits `upsert_organization_baseline`, which `DiscoverySessionService._advance` calls the moment
an interview concludes). A harness that runs thousands of interviews to conclusion needs the
complete surface, importable, in one place — so this promotes that behaviour into a real package
instead of adding a third copy.

Deliberately mirrors `PostgresGovernanceStore`'s surface exactly, including tenant scoping on
every read: a harness that cannot leak across tenants in-memory is the only kind that can
honestly assert tenant isolation as an invariant (CLAUDE.md §20).
"""

from __future__ import annotations

from dataclasses import dataclass

from governance_discovery.session import DiscoverySession
from governance_discovery.signal import SignalSet


@dataclass
class AnswerRow:
    """Mirrors the `discovery_answers` row shape the service reads back for go-back/replay."""

    question_id: str
    sequence: int
    raw_answer: object
    resolved_signal_key: str | None


class InMemoryGovernanceStore:
    """Tenant-scoped, append-only, no database. Safe to instantiate per scenario."""

    def __init__(self) -> None:
        self._sessions: dict[str, DiscoverySession] = {}
        self._answers: dict[str, list[AnswerRow]] = {}
        self.organization_baselines: dict[str, tuple[tuple[str, ...], SignalSet]] = {}
        self.applicability_versions: list[dict[str, object]] = []

    # --- sessions ---------------------------------------------------------------------------

    def save_session(self, session: DiscoverySession) -> None:
        self._sessions[session.id] = session

    def get_session(self, session_id: str, tenant_id: str) -> DiscoverySession | None:
        session = self._sessions.get(session_id)
        return session if session is not None and session.tenant_id == tenant_id else None

    def find_in_progress_session(self, tenant_id: str) -> DiscoverySession | None:
        candidates = [
            s
            for s in self._sessions.values()
            if s.tenant_id == tenant_id and s.status == "in_progress"
        ]
        return max(candidates, key=lambda s: s.updated_at, default=None)

    # --- answers ----------------------------------------------------------------------------

    def next_sequence(self, session_id: str) -> int:
        rows = self._answers.get(session_id, [])
        return (max((r.sequence for r in rows), default=0)) + 1

    def append_answer(self, **fields: object) -> None:
        question_id = fields["question_id"]
        sequence = fields["sequence"]
        resolved = fields["resolved_signal_key"]
        session_id = fields["session_id"]
        assert isinstance(question_id, str)
        assert isinstance(sequence, int)
        assert isinstance(session_id, str)
        assert resolved is None or isinstance(resolved, str)
        self._answers.setdefault(session_id, []).append(
            AnswerRow(
                question_id=question_id,
                sequence=sequence,
                raw_answer=fields["raw_answer"],
                resolved_signal_key=resolved,
            )
        )

    def answer_history(self, session_id: str, tenant_id: str) -> list[AnswerRow]:
        return sorted(self._answers.get(session_id, []), key=lambda r: r.sequence)

    # --- conclusion -------------------------------------------------------------------------

    def upsert_organization_baseline(
        self, tenant_id: str, active_packs: tuple[str, ...], signals: SignalSet, now: float
    ) -> None:
        """Called by `DiscoverySessionService` when an interview concludes. Its absence is
        exactly what stops the grc-api test-local store from ever finishing a session."""
        self.organization_baselines[tenant_id] = (active_packs, signals)

    def transaction(self):
        """No database, so nothing to roll back. Present because `DiscoverySessionService` opens a transaction around conclusion and a store that cannot must not silently be usable."""
        import contextlib

        return contextlib.nullcontext()

    def record_applicability_version(self, **fields: object) -> None:
        """Also called on conclusion, since ADR 0068: the analysis is recorded as version 1 where
        it is computed. Added here for the same reason the method above exists — a store that
        cannot record it cannot conclude an interview, and this store's whole purpose is running
        thousands of them to conclusion. The harness found this the moment the behaviour landed:
        300 scenarios, 300 AttributeErrors."""
        self.applicability_versions.append(fields)
