"""`DiscoverySessionService` — composes the `governance-discovery` engine (Tier A/B) with
`governance-store` persistence into the four operations the interview UI needs: start, answer,
go back, resume (ADR 0066). Owns sequencing and boundary validation only; every actual decision
(which question, when to conclude, what the analysis says) is made by the pure engine.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from governance_discovery.analysis import Applicability, analyze
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.pack import Question
from governance_discovery.session import DiscoverySession
from governance_discovery.signal import SignalSet

from governance_session.answer_resolution import resolve_signal
from governance_session.errors import (
    InvalidAnswer,
    NoQuestionToGoBackTo,
    QuestionNotCurrentlyEligible,
    SessionAlreadyConcluded,
    SessionNotFound,
    UnknownQuestion,
)

CORE_CONCLUSION = "core_conclusion"


def _signals_hash(signals: SignalSet) -> str:
    """A fingerprint of the answers behind a version, so a reader can tell "the same answers" from
    "the same result"."""
    return hashlib.sha256(
        json.dumps(signals.as_dict(), sort_keys=True, default=str).encode()
    ).hexdigest()


class AnswerHistoryRecord(Protocol):
    question_id: str
    sequence: int
    raw_answer: object


class GovernanceStorePort(Protocol):
    """The subset of `PostgresGovernanceStore`'s surface this service depends on — a Protocol so
    tests can supply a lightweight in-memory fake without a database."""

    def save_session(self, session: DiscoverySession) -> None: ...
    def get_session(self, session_id: str, tenant_id: str) -> DiscoverySession | None: ...
    def find_in_progress_session(self, tenant_id: str) -> DiscoverySession | None: ...
    def next_sequence(self, session_id: str) -> int: ...
    def append_answer(self, **fields: object) -> None: ...
    def answer_history(self, session_id: str, tenant_id: str) -> list[AnswerHistoryRecord]: ...
    def upsert_organization_baseline(
        self, tenant_id: str, active_packs: tuple[str, ...], signals: SignalSet, now: float
    ) -> None: ...
    def record_applicability_version(self, **fields: object) -> None: ...
    def transaction(self) -> object: ...   # a context manager; see `PostgresGovernanceStore`


@dataclass(frozen=True)
class AnswerOutcome:
    session: DiscoverySession
    next_question: Question | None
    concluded: bool


@dataclass(frozen=True)
class GoBackTarget:
    question: Question
    previous_answer: object


class DiscoverySessionService:
    def __init__(
        self,
        engine: DiscoveryEngine,
        store: GovernanceStorePort,
        *,
        new_id: Callable[[], str],
        now: Callable[[], float],
    ) -> None:
        self._engine = engine
        self._store = store
        self._new_id = new_id
        self._now = now

    def _record_applicability_version(
        self, session: DiscoverySession, applicability: Applicability
    ) -> None:
        """Record the concluded analysis as version 1 (ADR 0068).

        Part of conclusion, not a consequence of it: `_advance` wraps this, `save_session` and the
        baseline in ONE transaction, so a session cannot end up concluded with no version recorded.
        If this raises, the whole conclusion rolls back. A plan built on an analysis nobody can name
        later is worse than a conclusion that failed loudly now.
        """
        from governance_store.codec import applicability_to_dict

        self._store.record_applicability_version(
            version_id=f"av_{self._new_id()}",
            tenant_id=session.tenant_id,
            session_id=session.id,
            version=1,
            source=CORE_CONCLUSION,
            applicability=applicability_to_dict(applicability),
            resolved_signals=[
                {
                    "signal_key": key,
                    "resolved_value": value,
                    "origin": "core_answer",
                    "outcome": "absent_filled",
                    "core_claim": {"value": value},
                    "sector_claims": [],
                }
                for key, value in sorted(session.signals.as_dict().items())
            ],
            conflicts=[],
            answer_set_hash=_signals_hash(session.signals),
            engine_pack_versions=dict(session.pack_versions or {}),
        )

    # --- start / resume ---------------------------------------------------------------------

    def start(self, tenant_id: str) -> tuple[DiscoverySession, Question | None]:
        session = DiscoverySession.start(self._new_id(), tenant_id, self._now())
        question = self._engine.next_question(session.state)
        session = session.presenting(question.id if question else None, self._now())
        self._store.save_session(session)
        return session, question

    def resume(self, tenant_id: str) -> tuple[DiscoverySession, Question | None] | None:
        session = self._store.find_in_progress_session(tenant_id)
        if session is None:
            return None
        return session, self._engine.next_question(session.state)

    def get(self, session_id: str, tenant_id: str) -> DiscoverySession:
        session = self._store.get_session(session_id, tenant_id)
        if session is None:
            raise SessionNotFound(session_id)
        return session

    # --- answering -----------------------------------------------------------------------

    def _require_in_progress_and_eligible(
        self, session: DiscoverySession, question_id: str
    ) -> Question:
        if session.status != "in_progress":
            raise SessionAlreadyConcluded(session.id)
        question = self._engine.question_by_id(question_id)
        if question is None:
            raise UnknownQuestion(question_id)
        # Not a hard product error — the user may be re-answering a question that a LATER answer
        # already made eligible again after a 'go back' edit, which is fine. What we refuse is a
        # question that was never, and still isn't, in scope at all.
        not_eligible = question not in self._engine.eligible_questions(session.state)
        if not_eligible and question_id not in session.answered_question_ids:
            raise QuestionNotCurrentlyEligible(question_id)
        return question

    def _advance(self, session: DiscoverySession) -> AnswerOutcome:
        """Shared tail for both `answer()` and `skip()`: check conclusion, otherwise compute and
        persist the next question. The only difference between the two callers is how `session`
        got its new answered-question-id / signals — this decides what happens next."""
        if self._engine.is_concluded(session.state):
            applicability: Applicability = analyze(session.signals, self._engine)
            session = session.concluded(applicability, self._now())
            # ONE transaction for the three writes that have no meaning apart (ADR 0068 §D5).
            # The store is autocommit, so before this each was its own commit and a failure on the
            # last left a session concluded with no analysis version — a plan could then be built
            # from an analysis nobody could name. `transaction()` opens an explicit block without
            # changing the connection's autocommit for any other caller.
            with self._store.transaction():
                self._store.save_session(session)
                # ADR 0066 §5.7: the baseline `effective_signals()` (Plan Execution, §5.3) builds
                # on — without this, organization_profiles never gets a first writer, and
                # completing a plan item later would have nothing to layer its signal on top of.
                self._store.upsert_organization_baseline(
                    session.tenant_id, session.active_pack_ids, session.signals, self._now()
                )
                # v1 is written HERE, where the analysis is computed — not later, and not by
                # whoever happens to need it first.
                self._record_applicability_version(session, applicability)
            return AnswerOutcome(session=session, next_question=None, concluded=True)

        next_question = self._engine.next_question(session.state)
        session = session.presenting(next_question.id if next_question else None, self._now())
        self._store.save_session(session)
        return AnswerOutcome(session=session, next_question=next_question, concluded=False)

    def answer(
        self, session_id: str, tenant_id: str, question_id: str, raw_answer: object
    ) -> AnswerOutcome:
        session = self.get(session_id, tenant_id)
        question = self._require_in_progress_and_eligible(session, question_id)
        signal = resolve_signal(question, raw_answer)

        sequence = self._store.next_sequence(session_id)
        self._store.append_answer(
            answer_id=self._new_id(),
            session_id=session_id,
            tenant_id=tenant_id,
            sequence=sequence,
            question_id=question_id,
            question_version=question.version,
            raw_answer=raw_answer,
            resolved_signal_key=question.writes_signal,
            resolved_signal_value=signal.value,
            normalized_by="direct",
            llm_model_version=None,
            llm_confidence=None,
            created_at=self._now(),
        )

        updated_signals = session.signals.with_signal(signal)
        active_packs = self._engine.active_packs(updated_signals)
        session = session.with_answer(
            question_id=question_id,
            signal_key=question.writes_signal,
            signal=signal,
            active_pack_ids=tuple(p.pack_id for p in active_packs),
            pack_versions={p.pack_id: p.version for p in active_packs},
            now=self._now(),
        )
        return self._advance(session)

    def skip(self, session_id: str, tenant_id: str, question_id: str) -> AnswerOutcome:
        """Marks an OPTIONAL question as answered with no signal written — advances the
        interview exactly like `answer()` without polluting the SignalSet with a placeholder
        value. Required questions cannot be skipped (CLAUDE.md §22: validated at the boundary)."""
        session = self.get(session_id, tenant_id)
        question = self._require_in_progress_and_eligible(session, question_id)
        if question.required:
            raise InvalidAnswer(question_id, "required questions cannot be skipped")

        sequence = self._store.next_sequence(session_id)
        self._store.append_answer(
            answer_id=self._new_id(),
            session_id=session_id,
            tenant_id=tenant_id,
            sequence=sequence,
            question_id=question_id,
            question_version=question.version,
            raw_answer=None,
            resolved_signal_key=None,
            resolved_signal_value=None,
            normalized_by="skipped",
            llm_model_version=None,
            llm_confidence=None,
            created_at=self._now(),
        )
        session = session.with_answered_only(question_id=question_id, now=self._now())
        return self._advance(session)

    # --- go back --------------------------------------------------------------------------

    def go_back(self, session_id: str, tenant_id: str) -> GoBackTarget:
        """The most recently answered question that is STILL in scope — quietly skipping any
        answer a later edit made irrelevant (ADR 0066: 'quietly reroute, never confuse the
        user'). The client re-presents it pre-filled with `previous_answer`; submitting a new
        answer supersedes it via the normal `answer()` path (a fresh, later sequence)."""
        session = self.get(session_id, tenant_id)
        in_scope_ids = {
            q.id for pack in self._engine.active_packs(session.signals) for q in pack.questions
        }
        history = self._store.answer_history(session_id, tenant_id)
        for record in reversed(history):
            if record.question_id in in_scope_ids:
                question = self._engine.question_by_id(record.question_id)
                if question is not None:
                    return GoBackTarget(question=question, previous_answer=record.raw_answer)
        raise NoQuestionToGoBackTo(session_id)
