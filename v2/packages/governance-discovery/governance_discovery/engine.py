"""Tier A — live question routing (ADR 0066 §2.1, §2.4).

Runs after every answer. Its ONLY job is choosing the next question (or deciding the interview is
done) by recomputing, from the live SignalSet, which Knowledge Packs are active and which of their
questions are eligible. It never fires a rule, never recommends a framework, never scores maturity
or capacity, and nothing it computes is rendered to the user beyond "the next question" — that is
what Tier B (`analysis.py`) is for, run exactly once, at conclusion.
"""

from __future__ import annotations

from dataclasses import dataclass

from governance_discovery.pack import KnowledgePack, Question
from governance_discovery.predicate import evaluate, references_signal
from governance_discovery.signal import SignalSet

# A question at or above this priority must be answered (if it ever becomes eligible) before the
# interview may conclude — see `DiscoveryEngine.is_concluded` and `required_question_coverage`.
REQUIRED_PRIORITY_THRESHOLD = 5

# Earlier stages are asked before later ones, all else equal (ADR 0066 §2.4). Public: this fixed,
# small sequence is also what the interview UI's segmented progress indicator maps to — a stage
# name, never a raw question count (which varies session to session by design).
STAGE_ORDER = ("general", "structural", "sector_specific", "risk_deepdive")


def _stage_rank(stage: str) -> int:
    try:
        return STAGE_ORDER.index(stage)
    except ValueError:
        return len(STAGE_ORDER)  # unknown stages sort last, never crash


@dataclass(frozen=True)
class DiscoverySessionState:
    signals: SignalSet
    answered_question_ids: frozenset[str] = frozenset()


class DiscoveryEngine:
    def __init__(self, packs: dict[str, KnowledgePack]):
        self._packs = packs

    def pack_by_id(self, pack_id: str) -> KnowledgePack | None:
        """Looked up across every loaded pack — used to resolve a persisted
        `active_pack_ids`/`active_packs` list of ids back into real `KnowledgePack` objects (e.g.
        Plan Execution's maturity recalculation, ADR 0066 §5.3, which has no `SignalSet` to derive
        active packs from — the packs were fixed when the org's baseline was captured)."""
        return self._packs.get(pack_id)

    def question_by_id(self, question_id: str) -> Question | None:
        """Looked up across EVERY loaded pack, not just currently-active ones — a 'go back' or
        answer-validation request may reference a question from a pack that was active when it
        was originally answered."""
        for pack in self._packs.values():
            for question in pack.questions:
                if question.id == question_id:
                    return question
        return None

    def active_packs(self, signals: SignalSet) -> list[KnowledgePack]:
        """Recomputed from the live SignalSet on every call — this is what makes pack activation
        (and therefore the whole interview) adaptive without a separate 'reroute' algorithm."""
        return [
            pack
            for pack in self._packs.values()
            if pack.is_always_active or evaluate(pack.activation_predicate, signals)
        ]

    def eligible_questions(self, state: DiscoverySessionState) -> list[Question]:
        active = self.active_packs(state.signals)
        eligible: list[Question] = []
        seen_ids: set[str] = set()
        for pack in active:
            for question in pack.questions:
                if question.id in state.answered_question_ids or question.id in seen_ids:
                    continue
                if evaluate(question.applicability_predicate, state.signals):
                    eligible.append(question)
                    seen_ids.add(question.id)
        return eligible

    def _information_gain(self, question: Question, active_packs: list[KnowledgePack]) -> int:
        return sum(
            1
            for pack in active_packs
            for rule in pack.rules
            if references_signal(rule.predicate, question.writes_signal)
        )

    def next_question(self, state: DiscoverySessionState) -> Question | None:
        active = self.active_packs(state.signals)
        candidates = self.eligible_questions(state)
        if not candidates:
            return None
        candidates.sort(
            key=lambda q: (
                _stage_rank(q.stage),
                -q.priority,
                -self._information_gain(q, active),
                q.id,  # final tie-break: deterministic, never arbitrary dict/set ordering
            )
        )
        return candidates[0]

    @staticmethod
    def _counts_as_required(question: Question) -> bool:
        """A question counts toward conclusion/confidence only if BOTH its priority clears the
        threshold AND it isn't explicitly marked optional (`required=False` — free-text
        clarifications, supplementary multi-select context, ADR 0066 §2 UI extension)."""
        return question.required and question.priority >= REQUIRED_PRIORITY_THRESHOLD

    def is_concluded(self, state: DiscoverySessionState) -> bool:
        """No remaining eligible question is 'required' — the interview has nothing left worth
        asking. Sparse/contradictory answers can trigger this early; Tier B handles that
        explicitly via a low confidence_score rather than the interview looping forever
        (CLAUDE.md §6 pillar 16, fail-safe)."""
        return not any(self._counts_as_required(q) for q in self.eligible_questions(state))

    def required_question_coverage(self, signals: SignalSet) -> tuple[int, int]:
        """`(answered_required, total_required)` across every question that is BOTH required and
        actually in scope for this organization (its `applicability_predicate` holds against the
        given, typically final, SignalSet) in the packs active for that SignalSet — a question
        gated on a condition that never applies (e.g. 'last policy review date' when there is no
        approved policy) must never permanently cap confidence below 1.0. This is the basis for
        both Tier A's implicit progress and Tier B's `confidence_score` (ADR 0066 §2.4), so both
        use one shared definition of 'required'."""
        active = self.active_packs(signals)
        required = [
            q
            for pack in active
            for q in pack.questions
            if self._counts_as_required(q) and evaluate(q.applicability_predicate, signals)
        ]
        answered = [q for q in required if signals.has(q.writes_signal)]
        return len(answered), len(required)
