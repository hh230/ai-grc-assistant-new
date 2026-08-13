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
`TemplateQuestion.parse` rejects them outright rather than ignoring them, because a field that is
silently dropped today is a field someone relies on tomorrow.

**Three concepts, deliberately kept apart**, because conflating them is how a "sector" field
becomes the axis of a system it was only ever meant to index:

  * `Industry`          — a name and a slug. NO logic. It exists to be chosen from, nothing else.
  * `KnowledgeTemplate` — a versioned, reviewed body of questions FOR an industry.
  * `TemplateSelection` — which template version(s) a given organization was actually interviewed
                          under, and whether a human overrode the suggestion.

An interview binds to a **template version**, never to an industry name. Real estate will have v1,
v2 and v3; a report written in 2026 must remain explicable in 2029, which means knowing the
organization answered v1's questions — not today's. In a compliance product that is a requirement,
not a nicety.

None of this reaches the decision engine or the signal space. `primary_activity` remains a signal
because the engine derives obligations from it (a government-linked organization falls under a
different regime); what is new here — the Industry entity, the templates, the selection — is
knowledge and provenance, and stays out of the rules entirely.

Nothing here talks to a database or an LLM. It is the shape of the asset and the rules of its
lifecycle; `governance-store` persists it, and the generation tool produces it.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

# Knowledge has ONE source of truth. Claude generates Arabic and only Arabic; every other
# language is a derived translation with its own review lifecycle. Generating both at once would
# mean depending on two texts staying semantically identical — and the first reviewer who edits
# only the Arabic, or regenerates only the English, silently forks the question.
CANONICAL_LANGUAGE = "ar"

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


class IndustryStatus(str, enum.Enum):
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(frozen=True)
class Industry:
    """A name and a slug. Nothing else, on purpose.

    The pull towards `parent_industry`, `aliases`, `icon`, `regulatory_family` is real and should
    be resisted: every one of those turns a lookup value into the axis of the system, and the
    system's axis is the rule engine. An industry exists to be chosen from so a template can be
    found. Anything an industry "implies" belongs in derivations (`derivation.py`), where it is
    auditable, or on the template, where it is reviewed.

    Retiring one never invalidates history: an interview cites `(industry_slug, version)`, so a
    retired industry keeps explaining the reports produced under it.
    """

    slug: str
    canonical_name_ar: str
    status: IndustryStatus = IndustryStatus.ACTIVE

    @property
    def is_selectable(self) -> bool:
        return self.status is IndustryStatus.ACTIVE

    def as_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "canonical_name_ar": self.canonical_name_ar,
            "status": self.status.value,
        }


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


class KnowledgeTemplateError(ValueError):
    """Generated content that cannot be trusted as a knowledge asset."""


class IllegalTransitionError(KnowledgeTemplateError):
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
class Reference:
    """What a question rests on. A LABEL for the reviewer — never a citation the product presents
    to a customer as authority; only the Framework Library may assert what a framework requires.

    `clause` is optional on purpose. Demanding one for every reference would push the model to
    invent clause numbers, which is the exact failure this whole design exists to prevent: an
    invented citation reads more convincing than a missing one.
    """

    framework: str
    clause: str = ""

    @staticmethod
    def parse(raw: Any, *, where: str) -> Reference:
        if not isinstance(raw, dict):
            raise KnowledgeTemplateError(f"{where}: each reference must be an object")
        framework = raw.get("framework")
        if not isinstance(framework, str) or not framework.strip():
            raise KnowledgeTemplateError(f"{where}: a reference needs a non-empty 'framework'")
        clause = raw.get("clause") or ""
        if not isinstance(clause, str):
            raise KnowledgeTemplateError(f"{where}: 'clause' must be a string when present")
        return Reference(framework=framework.strip(), clause=clause.strip())

    def as_dict(self) -> dict[str, str]:
        return {"framework": self.framework, "clause": self.clause}


@dataclass(frozen=True)
class TemplateQuestion:
    """One question inside a template. Editorial metadata only — see the module docstring."""

    id: str
    # The Arabic text, and the ONLY authored text. Every other language is a derived
    # `QuestionTranslation` with its own review lifecycle.
    canonical_text: str
    type: str
    required: bool
    category: str
    importance: str
    # A question may rest on several clauses at once; a single `framework` string forced a false
    # reduction of exactly the thing a reviewer needs to see in full.
    references: tuple[Reference, ...]
    # REVIEWER-ONLY. Never rendered to a customer. It exists so that in two years someone can open
    # a question and learn why it is asked without reading the prompt that produced it or finding
    # the person who ran it. `as_customer_dict` omits it structurally, not by convention.
    why_we_ask: str
    # What would prove the answer, if the product later asks for documents. Empty means the
    # question is self-attested. Captured NOW because retrofitting it means re-reviewing every
    # published question in every sector.
    evidence_required: tuple[str, ...] = ()
    options: tuple[str, ...] = ()

    @staticmethod
    def parse(raw: Any, *, index: int) -> TemplateQuestion:
        where = f"question[{index}]"
        if not isinstance(raw, dict):
            raise KnowledgeTemplateError(f"{where}: expected an object, got {type(raw).__name__}")

        intruding = sorted(FORBIDDEN_DECISION_FIELDS & set(raw))
        if intruding:
            raise KnowledgeTemplateError(
                f"{where}: generated questions may not carry decision fields {intruding}. "
                f"Claude authors language, not truth — anything the engine acts on (signals, "
                f"rules, severity, maturity, priority) must be reviewable data, not prompt output."
            )

        def text(name: str) -> str:
            value = raw.get(name)
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeTemplateError(f"{where}: '{name}' must be a non-empty string")
            return value.strip()

        question_type = text("type").lower()
        if question_type not in ALLOWED_QUESTION_TYPES:
            raise KnowledgeTemplateError(
                f"{where}: type {question_type!r} is not renderable; "
                f"expected one of {sorted(ALLOWED_QUESTION_TYPES)}"
            )

        importance = text("importance").lower()
        if importance not in ALLOWED_IMPORTANCE:
            raise KnowledgeTemplateError(
                f"{where}: importance {importance!r} is not one of {sorted(ALLOWED_IMPORTANCE)}"
            )

        options = raw.get("options") or ()
        if not isinstance(options, (list, tuple)) or not all(isinstance(o, str) for o in options):
            raise KnowledgeTemplateError(f"{where}: 'options' must be a list of strings")
        options = tuple(o.strip() for o in options if o and o.strip())
        if question_type == "enum" and len(options) < 2:
            raise KnowledgeTemplateError(
                f"{where}: an enum question needs at least two options to be answerable"
            )

        required = raw.get("required", True)
        if not isinstance(required, bool):
            raise KnowledgeTemplateError(f"{where}: 'required' must be true or false")

        raw_references = raw.get("references")
        if not isinstance(raw_references, list) or not raw_references:
            raise KnowledgeTemplateError(
                f"{where}: 'references' must be a non-empty list of "
                f"{{framework, clause}} — a sector question a reviewer cannot trace to anything "
                f"is a question nobody can approve"
            )
        references = tuple(
            Reference.parse(r, where=f"{where}.references[{i}]")
            for i, r in enumerate(raw_references)
        )

        evidence = raw.get("evidence_required")
        # Absent is a mistake; EMPTY is a real answer meaning "self-attested". The difference
        # matters, so an omitted field is refused rather than defaulted to empty.
        if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
            raise KnowledgeTemplateError(
                f"{where}: 'evidence_required' must be a list of strings — use [] to state "
                f"explicitly that nothing can prove this answer"
            )

        return TemplateQuestion(
            id=text("id"),
            canonical_text=text("question"),
            type=question_type,
            required=required,
            category=text("category"),
            importance=importance,
            references=references,
            why_we_ask=text("why_we_ask"),
            evidence_required=tuple(e.strip() for e in evidence if e and e.strip()),
            options=options,
        )

    def as_customer_dict(self) -> dict[str, Any]:
        """What the interview may render. `why_we_ask` and the references are deliberately absent:
        one is a reviewer's note, the other is a label that must not read as a citation."""
        payload: dict[str, Any] = {
            "id": self.id,
            "question": self.canonical_text,
            "type": self.type,
            "required": self.required,
        }
        if self.options:
            payload["options"] = list(self.options)
        return payload

    def as_dict(self) -> dict[str, Any]:
        """The full asset, for storage and the review console."""
        payload: dict[str, Any] = {
            "id": self.id,
            "canonical_text": self.canonical_text,
            "type": self.type,
            "required": self.required,
            "category": self.category,
            "importance": self.importance,
            "references": [r.as_dict() for r in self.references],
            "why_we_ask": self.why_we_ask,
            "evidence_required": list(self.evidence_required),
        }
        if self.options:
            payload["options"] = list(self.options)
        return payload


@dataclass(frozen=True)
class KnowledgeTemplate:
    """A versioned, reviewed body of knowledge for one industry.

    `(industry_slug, version)` is its identity. An interview cites that pair forever; the industry
    row it points at may be renamed or retired without making an old report unreadable.
    """

    industry_slug: str
    version: int
    prompt_version: str
    generated_by: str
    questions: tuple[TemplateQuestion, ...]
    # What a plan for this sector is expected to contain — declared with the knowledge, so a
    # reviewer approves the shape of the deliverable, not only the questions.
    expected_outputs: tuple[str, ...] = ()
    review_status: TemplateStatus = TemplateStatus.GENERATED
    created_by: str = ""
    approved_by: str | None = None
    approved_at: float | None = None
    published_at: float | None = None
    notes: str = ""

    @property
    def version_id(self) -> str:
        """What an interview records. Stable, readable, and enough on its own to explain a report
        years later — `real_estate@v3`, not a surrogate key nobody can interpret."""
        return f"{self.industry_slug}@v{self.version}"

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
    ) -> KnowledgeTemplate:
        assert_transition(self.review_status, target)
        if target is TemplateStatus.APPROVED and not (actor or "").strip():
            raise KnowledgeTemplateError(
                "approving sector knowledge requires the approver's identity — it is the record "
                "of who accepted content every organization in this sector will be asked"
            )
        approved_by = actor if target is TemplateStatus.APPROVED else self.approved_by
        approved_at = at if target is TemplateStatus.APPROVED else self.approved_at
        # Stamped once, when it first becomes usable — the moment an asset started affecting real
        # organizations is the moment an auditor asks about.
        published_at = at if target is TemplateStatus.PUBLISHED else self.published_at
        return KnowledgeTemplate(
            industry_slug=self.industry_slug,
            version=self.version,
            prompt_version=self.prompt_version,
            generated_by=self.generated_by,
            questions=self.questions,
            expected_outputs=self.expected_outputs,
            review_status=target,
            created_by=self.created_by,
            approved_by=approved_by,
            approved_at=approved_at,
            published_at=published_at,
            notes=self.notes,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "industry_slug": self.industry_slug,
            "version": self.version,
            "version_id": self.version_id,
            "prompt_version": self.prompt_version,
            "generated_by": self.generated_by,
            "questions": [q.as_dict() for q in self.questions],
            "expected_outputs": list(self.expected_outputs),
            "review_status": self.review_status.value,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "published_at": self.published_at,
            "notes": self.notes,
        }


def parse_generated_template(
    payload: Any,
    *,
    industry_slug: str,
    version: int,
    prompt_version: str,
    generated_by: str,
    created_by: str = "",
) -> KnowledgeTemplate:
    """Turn one Claude response into a knowledge asset, or refuse it.

    Refusal is the point. An LLM response that is *almost* right is the dangerous case: it reads
    convincingly and would be asked of every organization in the sector.
    """
    if not isinstance(payload, dict):
        raise KnowledgeTemplateError(f"expected a JSON object, got {type(payload).__name__}")

    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise KnowledgeTemplateError("'questions' must be a non-empty list")

    questions = tuple(
        TemplateQuestion.parse(raw, index=i) for i, raw in enumerate(raw_questions)
    )

    seen: set[str] = set()
    for question in questions:
        if question.id in seen:
            raise KnowledgeTemplateError(
                f"duplicate question id {question.id!r} — answers are keyed by id, so a duplicate "
                f"silently overwrites an answer"
            )
        seen.add(question.id)

    expected = payload.get("expected_outputs") or ()
    if not isinstance(expected, (list, tuple)) or not all(isinstance(o, str) for o in expected):
        raise KnowledgeTemplateError("'expected_outputs' must be a list of strings")

    return KnowledgeTemplate(
        industry_slug=industry_slug,
        version=version,
        prompt_version=prompt_version,
        generated_by=generated_by,
        questions=questions,
        expected_outputs=tuple(o.strip() for o in expected if o and o.strip()),
        review_status=TemplateStatus.GENERATED,
        created_by=created_by,
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

    # The exact asset these answers came from — `real_estate@v3`. Not a sector name: when v4
    # publishes, this set must still identify the questions that were actually asked.
    template_version_id: str
    answers: tuple[SectorAnswer, ...] = field(default_factory=tuple)

    def with_answer(self, answer: SectorAnswer) -> SectorAnswerSet:
        kept = tuple(a for a in self.answers if a.question_id != answer.question_id)
        return SectorAnswerSet(
            template_version_id=self.template_version_id,
            answers=(*kept, answer),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "template_version_id": self.template_version_id,
            "answers": [a.as_dict() for a in self.answers],
        }


class TranslationStatus(str, enum.Enum):
    """A translation's own lifecycle, independent of the template's.

    Independence is the point. The Arabic can be reviewed without touching the English, the
    English without touching the Arabic, and a third language can be added without regenerating
    any knowledge — because none of them is the source of truth except Arabic.
    """

    GENERATED = "generated"
    REVIEWED = "reviewed"
    PUBLISHED = "published"


_ALLOWED_TRANSLATION_TRANSITIONS: dict[TranslationStatus, frozenset[TranslationStatus]] = {
    TranslationStatus.GENERATED: frozenset(
        {TranslationStatus.REVIEWED, TranslationStatus.GENERATED}
    ),
    TranslationStatus.REVIEWED: frozenset(
        {TranslationStatus.PUBLISHED, TranslationStatus.GENERATED}
    ),
    # Re-translating a published string is a new pass, not an edit in place.
    TranslationStatus.PUBLISHED: frozenset({TranslationStatus.GENERATED}),
}


@dataclass(frozen=True)
class QuestionTranslation:
    """One question rendered in one non-canonical language.

    Never authored alongside the question. Generating Arabic and English in a single call would
    make the product depend on two texts staying semantically identical, and the first reviewer to
    edit one of them forks the question silently — the same string drifting into two meanings with
    no record of which is authoritative.
    """

    question_id: str
    language: str
    text: str
    status: TranslationStatus = TranslationStatus.GENERATED

    def __post_init__(self) -> None:
        if self.language == CANONICAL_LANGUAGE:
            raise KnowledgeTemplateError(
                f"{CANONICAL_LANGUAGE!r} is the canonical language — it lives on the question "
                f"itself, and storing it again as a translation creates a second source of truth"
            )
        if not self.text.strip():
            raise KnowledgeTemplateError("a translation needs text")

    @property
    def is_usable(self) -> bool:
        return self.status is TranslationStatus.PUBLISHED

    def with_status(self, target: TranslationStatus) -> QuestionTranslation:
        if target not in _ALLOWED_TRANSLATION_TRANSITIONS[self.status]:
            allowed = sorted(s.value for s in _ALLOWED_TRANSLATION_TRANSITIONS[self.status])
            raise IllegalTransitionError(
                f"cannot move a translation from {self.status.value} to {target.value}; "
                f"allowed: {allowed}"
            )
        return QuestionTranslation(
            question_id=self.question_id,
            language=self.language,
            text=self.text,
            status=target,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "language": self.language,
            "text": self.text,
            "status": self.status.value,
        }


def translation_coverage(
    template: KnowledgeTemplate, translations: tuple[QuestionTranslation, ...], language: str
) -> tuple[int, int]:
    """`(published, total)` for one language — which languages are behind, answered with a number.

    Only PUBLISHED counts. A generated-but-unreviewed translation is not coverage; treating it as
    such is how an unreviewed string reaches a customer in a language nobody on the team reads.
    """
    if language == CANONICAL_LANGUAGE:
        return len(template.questions), len(template.questions)
    ids = {q.id for q in template.questions}
    # QUESTIONS, never rows. Since ADR 0069 a question is several translated parts, and counting
    # rows would report a sector as 7x covered because one question had seven parts. A question
    # counts once, and only because publication is all-or-nothing (`publish_question_translation`)
    # can its presence here be read as "this question is fully available in that language".
    published = {
        t.question_id
        for t in translations
        if t.language == language and t.is_usable and t.question_id in ids
    }
    return len(published), len(ids)


@dataclass(frozen=True)
class TemplateSelection:
    """Which template version(s) an organization was actually interviewed under.

    Two things this records that a plain `industry` column cannot.

    **The suggestion is not the decision.** `primary_activity` proposes a template; a human may
    disagree, and often should — reality is not one sector. A brokerage that also builds is
    "Construction + Real Estate"; a holding company is neither of its subsidiaries' sectors. So
    the selection holds a LIST, and remembers what was suggested so the two can be compared later.
    A suggestion the reviewer kept and a suggestion nobody looked at are different facts.

    **The version is the record.** `selected_version_ids` cites `real_estate@v3`, never
    `real_estate`. When v4 publishes, this organization's report stays readable because the exact
    questions it answered are still identifiable.
    """

    suggested_industry_slug: str
    selected_version_ids: tuple[str, ...]
    selected_by: str = ""
    selected_at: float | None = None

    def __post_init__(self) -> None:
        if not self.selected_version_ids:
            raise KnowledgeTemplateError(
                "an interview must cite at least one template version — an interview whose "
                "questions cannot be identified later cannot be explained later"
            )
        if len(set(self.selected_version_ids)) != len(self.selected_version_ids):
            raise KnowledgeTemplateError(
                f"duplicate template version in {list(self.selected_version_ids)}"
            )

    @property
    def was_overridden(self) -> bool:
        """True when the reviewer chose anything other than one template from the suggested
        industry — a second sector, or a different one entirely."""
        if len(self.selected_version_ids) != 1:
            return True
        return not self.selected_version_ids[0].startswith(f"{self.suggested_industry_slug}@v")

    def as_dict(self) -> dict[str, Any]:
        return {
            "suggested_industry_slug": self.suggested_industry_slug,
            "selected_version_ids": list(self.selected_version_ids),
            "was_overridden": self.was_overridden,
            "selected_by": self.selected_by,
            "selected_at": self.selected_at,
        }


def suggest_template(
    primary_activity: str, published: tuple[KnowledgeTemplate, ...]
) -> KnowledgeTemplate | None:
    """The newest published template for the answered activity — a SUGGESTION, nothing more.

    Returns `None` rather than guessing when no published template matches. A near-miss template
    is worse than none: the reviewer would be shown sector questions written for someone else and
    invited to accept them.
    """
    candidates = [
        t for t in published if t.industry_slug == primary_activity and t.is_usable
    ]
    return max(candidates, key=lambda t: t.version) if candidates else None
