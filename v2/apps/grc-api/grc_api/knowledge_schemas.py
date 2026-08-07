"""Request/response models for `/v1/knowledge/*` (ADR 0067).

Two views of a question exist, and the difference is **structural, not a flag**:

    ReviewQuestionView     everything, including `why_we_ask`
    InterviewQuestionView  no `why_we_ask` field at all

`why_we_ask` is written for a reviewer deciding whether a question deserves to exist. Showing a
customer "we ask this to determine whether you may broker at all" changes the answer they give.
A boolean like `include_why=False` would put one `if` between that text and a customer; a type that
has no such field cannot leak it however the route is called.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReferenceView(BaseModel):
    """What a question is grounded in. `clause` is optional on purpose — pressing the model for a
    clause number it does not know is how invented citations get created."""

    framework: str
    clause: str | None = None


def _reference_views(raw: Any) -> list[ReferenceView]:
    return [ReferenceView(**r) for r in (raw or [])]


class InterviewQuestionView(BaseModel):
    """What a customer is shown. Has no `why_we_ask` field to omit."""

    question_id: str
    canonical_text_ar: str
    type: str
    options: list[Any] = Field(default_factory=list)
    required: bool = True
    category: str
    importance: str
    references: list[ReferenceView] = Field(default_factory=list)
    evidence_required: list[str] = Field(default_factory=list)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> InterviewQuestionView:
        return cls(
            question_id=row["question_id"],
            canonical_text_ar=row["canonical_text_ar"],
            type=row["type"],
            options=list(row.get("options") or []),
            required=bool(row.get("required", True)),
            category=row["category"],
            importance=row["importance"],
            references=_reference_views(row.get("references")),
            evidence_required=list(row.get("evidence_required") or []),
        )


class ReviewQuestionView(InterviewQuestionView):
    """What a reviewer is shown: the same question plus the case for its existence."""

    why_we_ask: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ReviewQuestionView:
        return cls(
            **InterviewQuestionView.from_row(row).model_dump(),
            why_we_ask=row.get("why_we_ask") or "",
        )


class ReleaseView(BaseModel):
    """A release as the review console sees it — content, lifecycle state, and the provenance that
    makes it reproducible (`generated_by_model`, `prompt_version`, `generator_commit`)."""

    id: str
    industry_slug: str
    version: int
    status: str
    generated_by_model: str
    prompt_version: str
    generator_commit: str
    created_by: str
    approved_by: str | None = None
    approved_at: Any | None = None
    released_at: Any | None = None
    questions: list[ReviewQuestionView] | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ReleaseView:
        questions = row.get("questions")
        return cls(
            id=row["id"],
            industry_slug=row["industry_slug"],
            version=row["version"],
            status=row["status"],
            generated_by_model=row["generated_by_model"],
            prompt_version=row["prompt_version"],
            generator_commit=row["generator_commit"],
            created_by=row["created_by"],
            approved_by=row.get("approved_by"),
            approved_at=row.get("approved_at"),
            released_at=row.get("released_at"),
            questions=(
                [ReviewQuestionView.from_row(q) for q in questions]
                if questions is not None
                else None
            ),
        )


class ReleaseListResponse(BaseModel):
    releases: list[ReleaseView]


class IndustryView(BaseModel):
    slug: str
    canonical_name_ar: str
    status: str


class IndustryListResponse(BaseModel):
    industries: list[IndustryView]


class ActiveReleaseView(BaseModel):
    """What an interview loads. Deliberately a different shape from `ReleaseView`: the customer
    side has no business seeing draft lifecycle metadata or reviewer notes."""

    release_id: str
    industry_slug: str
    version: int
    activated_at: Any
    questions: list[InterviewQuestionView]

    @classmethod
    def from_row(cls, industry_slug: str, row: dict[str, Any]) -> ActiveReleaseView:
        return cls(
            release_id=row["id"],
            industry_slug=industry_slug,
            version=row["version"],
            activated_at=row["activated_at"],
            questions=[InterviewQuestionView.from_row(q) for q in row.get("questions") or []],
        )


class ActivationRecordView(BaseModel):
    release_id: str
    activated_by: str
    activated_at: Any
    reason: str


class ActivationHistoryResponse(BaseModel):
    activations: list[ActivationRecordView]


class OutcomeResponse(BaseModel):
    """The uniform write response: what changed, and what it means.

    `changed=false` is a success, not an error — every guarded write is idempotent, so submitting
    twice is a no-op. The client is told which of the two happened instead of having to infer it.
    """

    changed: bool
    event: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_outcome(cls, outcome: Any) -> OutcomeResponse:
        return cls(
            changed=outcome.changed,
            event=outcome.event.name if outcome.event else None,
            data=dict(outcome.data),
        )


# --- request bodies ---------------------------------------------------------------------------


class RegisterIndustryBody(BaseModel):
    slug: str = Field(min_length=1)
    canonical_name_ar: str = Field(min_length=1)


class GenerateReleaseBody(BaseModel):
    industry_slug: str = Field(min_length=1)


class ActivateReleaseBody(BaseModel):
    release_id: str = Field(min_length=1)
    # Why the pointer moved. A rollback and a routine upgrade are the same call and read
    # identically without it.
    reason: str = ""


class StartAssessmentBody(BaseModel):
    organization_id: str = Field(min_length=1)
    # What `primary_activity` suggested, and what a human actually chose. Both are stored, because
    # a suggestion someone examined and one nobody looked at are different facts.
    suggested_industry_slug: str | None = None
    selected_release_ids: list[str] = Field(min_length=1)
    source_session_id: str | None = None


class SectorAnswerBody(BaseModel):
    release_id: str = Field(min_length=1)
    question_id: str = Field(min_length=1)
    answer: Any = None


class RecordAnswersBody(BaseModel):
    answers: list[SectorAnswerBody] = Field(min_length=1)


class PlanContextResponse(BaseModel):
    """The concluded assessment, its selection, and every answer joined to the question it
    answers — the input a governance plan is built from."""

    assessment: dict[str, Any]
    selection: dict[str, Any] | None
    sector_answers: list[dict[str, Any]]
