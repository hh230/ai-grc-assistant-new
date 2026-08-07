"""Sector Knowledge Packs — the asset, its lifecycle, and the line Claude may not cross.

Most of this file feeds the parser content that is *almost* right, because that is the dangerous
case: an LLM response that reads convincingly and would then be asked of every organization in
the sector.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from governance_discovery.sector_template import (
    FORBIDDEN_DECISION_FIELDS,
    IllegalTransitionError,
    SectorAnswer,
    SectorAnswerSet,
    SectorTemplate,
    SectorTemplateError,
    TemplateStatus,
    assert_transition,
    can_transition,
    parse_generated_template,
)


def _question(**overrides) -> dict:
    base = {
        "id": "fal_license",
        "question": "هل لديكم رخصة فال سارية؟",
        "type": "boolean",
        "required": True,
        "category": "licensing",
        "importance": "critical",
        "framework": "General Saudi Real Estate",
        "reason": "Brokerage activity without a valid FAL licence is not permitted.",
    }
    base.update(overrides)
    return base


def _payload(**overrides) -> dict:
    base = {"questions": [_question()], "expected_outputs": ["licensing status"]}
    base.update(overrides)
    return base


def _parse(payload: dict) -> SectorTemplate:
    return parse_generated_template(
        payload,
        sector="real_estate",
        version=1,
        prompt_version="sector_questions.v1",
        generated_by="claude-sonnet-5",
    )


# --- the line: language, not truth -----------------------------------------------------------


@pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_DECISION_FIELDS))
def test_a_generated_question_may_not_carry_ANY_decision_field(forbidden):
    """The owner's rule, made mechanical: no regulatory fact or compliance decision lives inside a
    prompt's output. Every one of these fields would put LLM output on the decision path."""
    with pytest.raises(SectorTemplateError, match="decision fields"):
        _parse(_payload(questions=[_question(**{forbidden: "anything"})]))


def test_the_refusal_names_the_offending_field_and_says_why():
    """A rejection a reviewer cannot act on is a rejection that gets worked around."""
    with pytest.raises(SectorTemplateError) as caught:
        _parse(_payload(questions=[_question(writes_signal="has_fal_license")]))
    message = str(caught.value)
    assert "writes_signal" in message
    assert "language, not truth" in message


def test_editorial_metadata_IS_allowed_and_preserved():
    """The distinction is not "no metadata" — it is metadata a human reads versus metadata the
    engine acts on."""
    template = _parse(_payload())
    question = template.questions[0]
    assert question.category == "licensing"
    assert question.importance == "critical"
    assert question.framework == "General Saudi Real Estate"
    assert question.reason.startswith("Brokerage activity")


# --- refusing content that is *almost* right --------------------------------------------------


def test_an_unrenderable_question_type_is_refused():
    """The sector questions are rendered by the SAME interview UI as the hand-authored ones, so a
    type nothing can display is a broken interview, not a cosmetic issue."""
    with pytest.raises(SectorTemplateError, match="not renderable"):
        _parse(_payload(questions=[_question(type="matrix")]))


def test_an_enum_with_fewer_than_two_options_is_refused():
    with pytest.raises(SectorTemplateError, match="at least two options"):
        _parse(_payload(questions=[_question(type="enum", options=["yes"])]))


def test_duplicate_ids_are_refused_because_answers_are_keyed_by_id():
    with pytest.raises(SectorTemplateError, match="duplicate question id"):
        _parse(_payload(questions=[_question(), _question(question="asked differently")]))


def test_an_invented_importance_is_refused():
    with pytest.raises(SectorTemplateError, match="importance"):
        _parse(_payload(questions=[_question(importance="extremely critical")]))


def test_a_question_missing_its_reason_is_refused():
    """`reason` is what a reviewer reads to decide whether to approve. Without it the review is a
    rubber stamp."""
    incomplete = _question()
    del incomplete["reason"]
    with pytest.raises(SectorTemplateError, match="'reason'"):
        _parse(_payload(questions=[incomplete]))


def test_an_empty_question_list_is_refused():
    with pytest.raises(SectorTemplateError, match="non-empty list"):
        _parse(_payload(questions=[]))


def test_a_non_object_response_is_refused():
    with pytest.raises(SectorTemplateError, match="expected a JSON object"):
        _parse("[]")  # type: ignore[arg-type]


# --- lifecycle --------------------------------------------------------------------------------


def test_a_freshly_generated_template_is_NOT_usable():
    """The whole reason this workflow exists: raw generation must never reach a customer."""
    template = _parse(_payload())
    assert template.review_status is TemplateStatus.GENERATED
    assert template.is_usable is False


def test_only_published_is_usable():
    template = _parse(_payload())
    for status in TemplateStatus:
        at_status = replace(template, review_status=status)
        assert at_status.is_usable is (status is TemplateStatus.PUBLISHED)


def test_the_happy_path_runs_generated_to_published_to_deprecated():
    template = _parse(_payload())
    template = template.with_status(TemplateStatus.NEEDS_REVIEW)
    template = template.with_status(TemplateStatus.APPROVED, actor="reviewer@example.com", at=10.0)
    assert template.approved_by == "reviewer@example.com"
    assert template.approved_at == 10.0

    template = template.with_status(TemplateStatus.PUBLISHED)
    assert template.is_usable is True

    template = template.with_status(TemplateStatus.DEPRECATED)
    assert template.is_usable is False


def test_generated_cannot_jump_straight_to_published():
    """Skipping review is the failure this asset type exists to prevent."""
    template = _parse(_payload())
    with pytest.raises(IllegalTransitionError, match="cannot move"):
        template.with_status(TemplateStatus.PUBLISHED)


def test_a_reviewer_can_send_it_back_to_be_regenerated():
    template = _parse(_payload()).with_status(TemplateStatus.NEEDS_REVIEW)
    assert template.with_status(TemplateStatus.GENERATED).review_status is TemplateStatus.GENERATED


def test_approving_without_an_identity_is_refused():
    """`approved_by` is the record of who accepted content every organization in this sector will
    be asked. An anonymous approval is not an approval."""
    template = _parse(_payload()).with_status(TemplateStatus.NEEDS_REVIEW)
    with pytest.raises(SectorTemplateError, match="approver's identity"):
        template.with_status(TemplateStatus.APPROVED, actor="  ")


def test_deprecated_is_terminal():
    assert not any(can_transition(TemplateStatus.DEPRECATED, s) for s in TemplateStatus)
    with pytest.raises(IllegalTransitionError, match="terminal"):
        assert_transition(TemplateStatus.DEPRECATED, TemplateStatus.PUBLISHED)


def test_a_published_template_cannot_be_edited_back_into_review():
    """Organizations interviewed under a published version must stay explicable, so a published
    asset is retired and replaced rather than changed underneath them."""
    template = (
        _parse(_payload())
        .with_status(TemplateStatus.NEEDS_REVIEW)
        .with_status(TemplateStatus.APPROVED, actor="r@example.com", at=1.0)
        .with_status(TemplateStatus.PUBLISHED)
    )
    with pytest.raises(IllegalTransitionError):
        template.with_status(TemplateStatus.NEEDS_REVIEW)


# --- sector answers are their own layer -------------------------------------------------------


def test_a_sector_answer_is_not_a_signal():
    """`Discovery Answers -> Core Signals -> Sector Answers -> Plan Context`. A FAL licence is
    true of real estate and meaningless elsewhere; admitting it to the signal space would break
    the knowledge register's guarantee that every signal drives a rule."""
    answer = SectorAnswer(question_id="fal_license", question="FAL?", answer=False)
    assert not hasattr(answer, "writes_signal")
    assert set(answer.as_dict()) == {"question_id", "question", "answer", "category", "framework"}


def test_answering_the_same_question_twice_replaces_rather_than_duplicates():
    answers = SectorAnswerSet(sector="real_estate", template_version=1)
    answers = answers.with_answer(SectorAnswer("fal_license", "FAL?", False))
    answers = answers.with_answer(SectorAnswer("fal_license", "FAL?", True))
    assert len(answers.answers) == 1
    assert answers.answers[0].answer is True


def test_the_answer_set_records_which_template_version_produced_it():
    """Without it, an answer cannot be explained once the template is deprecated."""
    answers = SectorAnswerSet(sector="real_estate", template_version=3)
    assert answers.as_dict()["template_version"] == 3
