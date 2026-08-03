"""HTTP response shapes for the Governance Discovery interview (ADR 0066).

Representations hide implementation exactly like the rest of the host (`schemas.py`'s discipline):
a `QuestionView` exposes only what the interview UI needs to render one question (id, prompt key,
value type, options, presentation hint) — never the internal Signal key it writes, never any rule
or framework name. Progress is a fixed 4-stage indicator, never a raw question count (ADR 0066
"Frontend": the count varies session to session by design, so it is never shown).
"""

from __future__ import annotations

from typing import Any

from governance_discovery.engine import STAGE_ORDER
from governance_discovery.pack import Question
from pydantic import BaseModel


class QuestionView(BaseModel):
    id: str
    prompt_key: str
    value_type: str
    options: list[str] | None = None
    ui_hint: str | None = None
    allow_multiple: bool = False
    required: bool = True
    stage: str

    @classmethod
    def from_question(cls, question: Question) -> QuestionView:
        return cls(
            id=question.id,
            prompt_key=question.prompt_key,
            value_type=question.value_type.value,
            options=list(question.options) if question.options else None,
            ui_hint=question.ui_hint,
            allow_multiple=question.allow_multiple,
            required=question.required,
            stage=question.stage,
        )


class StageProgress(BaseModel):
    stage: str
    stage_index: int
    stage_count: int

    @classmethod
    def for_stage(cls, stage: str) -> StageProgress:
        index = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else len(STAGE_ORDER) - 1
        return cls(stage=stage, stage_index=index, stage_count=len(STAGE_ORDER))


class DiscoveryTurnResponse(BaseModel):
    """The shape returned by start/resume/answer alike: a session id, its status, and — while
    `in_progress` — exactly one next question and its stage progress. Once `concluded`, `question`
    and `progress` are both null; the client transitions to the short analysis screen and then
    fetches `/result` (ADR 0066 "Frontend": three strictly sequential states, never blended)."""

    session_id: str
    status: str
    question: QuestionView | None = None
    progress: StageProgress | None = None


class SubmitAnswerBody(BaseModel):
    question_id: str
    value: Any


class SkipQuestionBody(BaseModel):
    question_id: str


class GoBackResponse(BaseModel):
    question: QuestionView
    previous_answer: Any


class DiscoveryResultResponse(BaseModel):
    """A Phase-2 stopgap: the raw Tier B analysis, exposed once a session concludes. Phase 3's
    `generate_governance_plan` Mission (ADR 0066 §3) supersedes this as the real, approval-gated,
    trackable plan — this endpoint exists so the interview has somewhere to hand off to before
    that Mission exists."""

    frameworks: list[dict]
    maturity: dict
    maturity_vision: dict
    capacity: dict
    gaps: list[dict]
    plan_items: list[dict]
    confidence: str
    confidence_score: float
