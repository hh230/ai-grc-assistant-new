"""Sector Knowledge Packs — LLM-authored interview questions, held as reviewed knowledge assets.

The bundled packs (`packs/*.json`) are hand-authored, cross-sector, and drive the rule engine. They
answer "what is true of every organization". They do not, and should not, know that a Saudi real
estate brokerage needs a FAL licence — writing a rule set per sector by hand does not scale, which
is exactly why eight of nine industries produced identical plans.

A Sector Template fills that gap: Claude is asked ONCE per sector to design the sector-specific
half of the interview, and the result is stored, reviewed and published as a versioned asset. The
second customer in that sector costs nothing and gets the identical, already-reviewed questions.

**The line this module exists to enforce** (the owner's rule, made mechanical):

    Claude is responsible for LANGUAGE, not for TRUTH.

A generated question may carry *editorial* metadata — what it asks, why it is asked, which
regulator it relates to. It may **not** carry anything the decision engine would act on: no
signal to write, no rule, no severity, no maturity contribution, no priority. Those are decisions,
and decisions live in auditable rules, never inside a prompt whose reasoning nobody can replay.
`SectorQuestion.parse` rejects them outright rather than ignoring them, because a field that is
silently dropped today is a field someone relies on tomorrow.

Nothing here talks to a database or an LLM. It is the shape of the asset and the rules of its
lifecycle; `governance-store` persists it, and the generation tool produces it.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

# Answer shapes a generated question may use. Deliberately the same small vocabulary the
# hand-authored packs use — a sector question is rendered by the SAME interview UI, so it cannot
# invent an input type nothing can display.
ALLOWED_QUESTION_TYPES: frozenset[str] = frozenset(
    {"boolean", "enum", "numeric", "date", "text"}
)

# How much the sector expert thinks the answer matters. EDITORIAL — it orders the interview and
# informs the report's wording. It is deliberately NOT a severity: nothing computes a gap, a risk
# or a priority from it, because that is the rule engine's job.
ALLOWED_IMPORTANCE: frozenset[str] = frozenset({"critical", "high", "medium", "low"})

# Fields that would make a generated question part of the DECISION path. Named explicitly so the
# rejection message can say which one appeared and why it is refused.
FORBIDDEN_DECISION_FIELDS: frozenset[str] = frozenset(
    {
        "writes_signal",      # would inject an LLM-invented fact into the engine's signal space
        "signal",
        "rule",               # a rule must be reviewable data, not prompt output
        "rules",
        "predicate",
        "effect",
        "severity",           # gap severity is computed, never asserted
        "maturity_delta",     # maturity is scored by the engine
        "priority",           # priority is scheduled by the engine from capacity + dependencies
        "plan_seed",
        "resolves_signal",
    }
)


class TemplateStatus(str, enum.Enum):
    """The lifecycle of a knowledge asset.

    Generated output does not reach a customer until a human with the knowledge-approver role has
    published it. One bad question does not affect one plan — it affects **every organization in
    that sector**, which is why this has its own gate rather than reusing the per-mission one.
    """

    GENERATED = "generated"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


_ALLOWED_TRANSITIONS: dict[TemplateStatus, frozenset[TemplateStatus]] = {
    # Generation is not a submission: a draft may be regenerated repeatedly before anyone is asked
    # to spend review time on it.
    TemplateStatus.GENERATED: frozenset({TemplateStatus.NEEDS_REVIEW, TemplateStatus.GENERATED}),
    # A reviewer either accepts it or sends it back to be regenerated with a better prompt.
    TemplateStatus.NEEDS_REVIEW: frozenset({TemplateStatus.APPROVED, TemplateStatus.GENERATED}),
    TemplateStatus.APPROVED: frozenset({TemplateStatus.PUBLISHED, TemplateStatus.NEEDS_REVIEW}),
    # Superseded by a newer version, or withdrawn because it turned out to be wrong. Retiring is
    # the only exit: a published asset is never edited in place, because organizations interviewed
    # under it must remain explicable.
    TemplateStatus.PUBLISHED: frozenset({TemplateStatus.DEPRECATED}),
    TemplateStatus.DEPRECATED: frozenset(),
}

# The single status a customer interview may draw from.
USABLE_STATUS = TemplateStatus.PUBLISHED


class SectorTemplateError(ValueError):
    """Generated content that cannot be trusted as a knowledge asset."""


class IllegalTransitionError(SectorTemplateError):
    """A lifecycle move the review workflow does not permit."""


def can_transition(current: TemplateStatus, target: TemplateStatus) -> bool:
    return target in _ALLOWED_TRANSITIONS[current]


def assert_transition(current: TemplateStatus, target: TemplateStatus) -> None:
    if not can_transition(current, target):
        allowed = sorted(s.value for s in _ALLOWED_TRANSITIONS[current])
        raise IllegalTransitionError(
            f"cannot move a sector template from {current.value} to {target.value}; "
            f"allowed from {current.value}: {allowed or 'nothing — it is terminal'}"
        )


@dataclass(frozen=True)
class SectorQuestion:
    """One generated question. Editorial metadata only — see the module docstring."""

    id: str
    question: str
    type: str
    required: bool
    category: str
    importance: str
    # Which regulator or regime the question relates to. A LABEL for the reviewer and the report,
    # never a citation the product presents as authority: the Framework Library is the only thing
    # that may assert what a framework requires.
    framework: str
    reason: str
    options: tuple[str, ...] = ()

    @staticmethod
    def parse(raw: Any, *, index: int) -> SectorQuestion:
        where = f"question[{index}]"
        if not isinstance(raw, dict):
            raise SectorTemplateError(f"{where}: expected an object, got {type(raw).__name__}")

        intruding = sorted(FORBIDDEN_DECISION_FIELDS & set(raw))
        if intruding:
            raise SectorTemplateError(
                f"{where}: generated questions may not carry decision fields {intruding}. "
                f"Claude authors language, not truth — anything the engine acts on (signals, "
                f"rules, severity, maturity, priority) must be reviewable data, not prompt output."
            )

        def text(name: str) -> str:
            value = raw.get(name)
            if not isinstance(value, str) or not value.strip():
                raise SectorTemplateError(f"{where}: '{name}' must be a non-empty string")
            return value.strip()

        question_type = text("type").lower()
        if question_type not in ALLOWED_QUESTION_TYPES:
            raise SectorTemplateError(
                f"{where}: type {question_type!r} is not renderable; "
                f"expected one of {sorted(ALLOWED_QUESTION_TYPES)}"
            )

        importance = text("importance").lower()
        if importance not in ALLOWED_IMPORTANCE:
            raise SectorTemplateError(
                f"{where}: importance {importance!r} is not one of {sorted(ALLOWED_IMPORTANCE)}"
            )

        options = raw.get("options") or ()
        if not isinstance(options, (list, tuple)) or not all(isinstance(o, str) for o in options):
            raise SectorTemplateError(f"{where}: 'options' must be a list of strings")
        options = tuple(o.strip() for o in options if o and o.strip())
        if question_type == "enum" and len(options) < 2:
            raise SectorTemplateError(
                f"{where}: an enum question needs at least two options to be answerable"
            )

        required = raw.get("required", True)
        if not isinstance(required, bool):
            raise SectorTemplateError(f"{where}: 'required' must be true or false")

        return SectorQuestion(
            id=text("id"),
            question=text("question"),
            type=question_type,
            required=required,
            category=text("category"),
            importance=importance,
            framework=text("framework"),
            reason=text("reason"),
            options=options,
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "question": self.question,
            "type": self.type,
            "required": self.required,
            "category": self.category,
            "importance": self.importance,
            "framework": self.framework,
            "reason": self.reason,
        }
        if self.options:
            payload["options"] = list(self.options)
        return payload


@dataclass(frozen=True)
class SectorTemplate:
    """A versioned, reviewed body of sector knowledge."""

    sector: str
    version: int
    prompt_version: str
    generated_by: str
    questions: tuple[SectorQuestion, ...]
    # What a plan for this sector is expected to contain — declared with the knowledge, so a
    # reviewer approves the shape of the deliverable, not only the questions.
    expected_outputs: tuple[str, ...] = ()
    review_status: TemplateStatus = TemplateStatus.GENERATED
    approved_by: str | None = None
    approved_at: float | None = None
    notes: str = ""

    @property
    def is_usable(self) -> bool:
        """Whether a customer interview may draw on this. Only ever true when published."""
        return self.review_status is USABLE_STATUS

    def with_status(
        self,
        target: TemplateStatus,
        *,
        actor: str | None = None,
        at: float | None = None,
    ) -> SectorTemplate:
        assert_transition(self.review_status, target)
        if target is TemplateStatus.APPROVED and not (actor or "").strip():
            raise SectorTemplateError(
                "approving sector knowledge requires the approver's identity — it is the record "
                "of who accepted content every organization in this sector will be asked"
            )
        approved_by = actor if target is TemplateStatus.APPROVED else self.approved_by
        approved_at = at if target is TemplateStatus.APPROVED else self.approved_at
        return SectorTemplate(
            sector=self.sector,
            version=self.version,
            prompt_version=self.prompt_version,
            generated_by=self.generated_by,
            questions=self.questions,
            expected_outputs=self.expected_outputs,
            review_status=target,
            approved_by=approved_by,
            approved_at=approved_at,
            notes=self.notes,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "sector": self.sector,
            "version": self.version,
            "prompt_version": self.prompt_version,
            "generated_by": self.generated_by,
            "questions": [q.as_dict() for q in self.questions],
            "expected_outputs": list(self.expected_outputs),
            "review_status": self.review_status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "notes": self.notes,
        }


def parse_generated_template(
    payload: Any,
    *,
    sector: str,
    version: int,
    prompt_version: str,
    generated_by: str,
) -> SectorTemplate:
    """Turn one Claude response into a knowledge asset, or refuse it.

    Refusal is the point. An LLM response that is *almost* right is the dangerous case: it reads
    convincingly and would be asked of every organization in the sector.
    """
    if not isinstance(payload, dict):
        raise SectorTemplateError(f"expected a JSON object, got {type(payload).__name__}")

    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise SectorTemplateError("'questions' must be a non-empty list")

    questions = tuple(
        SectorQuestion.parse(raw, index=i) for i, raw in enumerate(raw_questions)
    )

    seen: set[str] = set()
    for question in questions:
        if question.id in seen:
            raise SectorTemplateError(
                f"duplicate question id {question.id!r} — answers are keyed by id, so a duplicate "
                f"silently overwrites an answer"
            )
        seen.add(question.id)

    expected = payload.get("expected_outputs") or ()
    if not isinstance(expected, (list, tuple)) or not all(isinstance(o, str) for o in expected):
        raise SectorTemplateError("'expected_outputs' must be a list of strings")

    return SectorTemplate(
        sector=sector,
        version=version,
        prompt_version=prompt_version,
        generated_by=generated_by,
        questions=questions,
        expected_outputs=tuple(o.strip() for o in expected if o and o.strip()),
        review_status=TemplateStatus.GENERATED,
    )


@dataclass(frozen=True)
class SectorAnswer:
    """One customer answer to a sector question.

    Deliberately NOT a Signal. A Signal is a fact the decision engine relies on, and every Signal
    must drive a rule (see `knowledge_register`). "Do you hold a FAL licence?" is true of real
    estate and meaningless everywhere else; admitting it to the signal space would break that
    guarantee for every sector added afterwards. Sector answers travel their own path:

        Discovery Answers -> Core Signals -> Sector Answers -> Plan Context
    """

    question_id: str
    question: str
    answer: Any
    category: str = ""
    framework: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "answer": self.answer,
            "category": self.category,
            "framework": self.framework,
        }


@dataclass
class SectorAnswerSet:
    """The sector half of one organization's interview."""

    sector: str
    template_version: int
    answers: tuple[SectorAnswer, ...] = field(default_factory=tuple)

    def with_answer(self, answer: SectorAnswer) -> SectorAnswerSet:
        kept = tuple(a for a in self.answers if a.question_id != answer.question_id)
        return SectorAnswerSet(
            sector=self.sector,
            template_version=self.template_version,
            answers=(*kept, answer),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "sector": self.sector,
            "template_version": self.template_version,
            "answers": [a.as_dict() for a in self.answers],
        }
