"""Sector Knowledge Packs — the asset, its lifecycle, and the line Claude may not cross.

Most of this file feeds the parser content that is *almost* right, because that is the dangerous
case: an LLM response that reads convincingly and would then be asked of every organization in
the sector.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from governance_discovery.knowledge_template import (
    CANONICAL_LANGUAGE,
    FORBIDDEN_DECISION_FIELDS,
    Industry,
    IndustryStatus,
    IllegalTransitionError,
    QuestionTranslation,
    SectorAnswer,
    SectorAnswerSet,
    KnowledgeTemplate,
    KnowledgeTemplateError,
    TemplateSelection,
    TemplateStatus,
    TranslationStatus,
    assert_transition,
    can_transition,
    parse_generated_template,
    suggest_template,
    translation_coverage,
)


def _question(**overrides) -> dict:
    base = {
        "id": "fal_license",
        "question": "هل لديكم رخصة فال سارية؟",
        "type": "boolean",
        "required": True,
        "category": "licensing",
        "importance": "critical",
        "references": [{"framework": "General Saudi Real Estate", "clause": "FAL"}],
        "why_we_ask": "Determines whether the organization may broker at all.",
        "evidence_required": ["License number", "Expiry date"],
    }
    base.update(overrides)
    return base


def _payload(**overrides) -> dict:
    base = {"questions": [_question()], "expected_outputs": ["licensing status"]}
    base.update(overrides)
    return base


def _parse(payload: dict) -> KnowledgeTemplate:
    return parse_generated_template(
        payload,
        industry_slug="real_estate",
        version=1,
        prompt_version="sector_questions.v1",
        generated_by="claude-sonnet-5",
    )


# --- the line: language, not truth -----------------------------------------------------------


@pytest.mark.parametrize("forbidden", sorted(FORBIDDEN_DECISION_FIELDS))
def test_a_generated_question_may_not_carry_ANY_decision_field(forbidden):
    """The owner's rule, made mechanical: no regulatory fact or compliance decision lives inside a
    prompt's output. Every one of these fields would put LLM output on the decision path."""
    with pytest.raises(KnowledgeTemplateError, match="decision fields"):
        _parse(_payload(questions=[_question(**{forbidden: "anything"})]))


def test_the_refusal_names_the_offending_field_and_says_why():
    """A rejection a reviewer cannot act on is a rejection that gets worked around."""
    with pytest.raises(KnowledgeTemplateError) as caught:
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
    assert question.references[0].framework == "General Saudi Real Estate"
    assert question.why_we_ask.startswith("Determines whether")


# --- refusing content that is *almost* right --------------------------------------------------


def test_an_unrenderable_question_type_is_refused():
    """The sector questions are rendered by the SAME interview UI as the hand-authored ones, so a
    type nothing can display is a broken interview, not a cosmetic issue."""
    with pytest.raises(KnowledgeTemplateError, match="not renderable"):
        _parse(_payload(questions=[_question(type="matrix")]))


def test_an_enum_with_fewer_than_two_options_is_refused():
    with pytest.raises(KnowledgeTemplateError, match="at least two options"):
        _parse(_payload(questions=[_question(type="enum", options=["yes"])]))


def test_duplicate_ids_are_refused_because_answers_are_keyed_by_id():
    with pytest.raises(KnowledgeTemplateError, match="duplicate question id"):
        _parse(_payload(questions=[_question(), _question(question="asked differently")]))


def test_an_invented_importance_is_refused():
    with pytest.raises(KnowledgeTemplateError, match="importance"):
        _parse(_payload(questions=[_question(importance="extremely critical")]))


def test_a_question_missing_why_we_ask_is_refused():
    """`why_we_ask` is what a reviewer reads to decide whether to approve. Without it the review is
    a rubber stamp, and in two years nobody can say why the question exists."""
    incomplete = _question()
    del incomplete["why_we_ask"]
    with pytest.raises(KnowledgeTemplateError, match="'why_we_ask'"):
        _parse(_payload(questions=[incomplete]))


def test_an_empty_question_list_is_refused():
    with pytest.raises(KnowledgeTemplateError, match="non-empty list"):
        _parse(_payload(questions=[]))


def test_a_non_object_response_is_refused():
    with pytest.raises(KnowledgeTemplateError, match="expected a JSON object"):
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
    with pytest.raises(KnowledgeTemplateError, match="approver's identity"):
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
    answers = SectorAnswerSet(template_version_id="real_estate@v1")
    answers = answers.with_answer(SectorAnswer("fal_license", "FAL?", False))
    answers = answers.with_answer(SectorAnswer("fal_license", "FAL?", True))
    assert len(answers.answers) == 1
    assert answers.answers[0].answer is True


def test_the_answer_set_records_which_template_version_produced_it():
    """Without it, an answer cannot be explained once the template is deprecated."""
    answers = SectorAnswerSet(template_version_id="real_estate@v3")
    assert answers.as_dict()["template_version_id"] == "real_estate@v3"


# --- references, evidence, and the reviewer/customer split ------------------------------------


def test_a_question_may_rest_on_SEVERAL_clauses():
    """A single `framework` string forced a false reduction of exactly what a reviewer needs."""
    template = _parse(_payload(questions=[_question(references=[
        {"framework": "ISO27001", "clause": "5.2"},
        {"framework": "ISO27001", "clause": "6.1"},
    ])]))
    assert [(r.framework, r.clause) for r in template.questions[0].references] == [
        ("ISO27001", "5.2"),
        ("ISO27001", "6.1"),
    ]


def test_a_reference_without_a_clause_is_allowed():
    """Demanding a clause for every reference would push the model to INVENT clause numbers — an
    invented citation reads more convincing than a missing one."""
    template = _parse(_payload(questions=[_question(references=[{"framework": "REGA"}])]))
    assert template.questions[0].references[0].clause == ""


def test_a_question_with_no_references_at_all_is_refused():
    with pytest.raises(KnowledgeTemplateError, match="references"):
        _parse(_payload(questions=[_question(references=[])]))


def test_empty_evidence_is_a_real_answer_but_a_MISSING_field_is_not():
    """`[]` means "self-attested"; an omitted field means nobody decided. The difference is the
    whole value of capturing it now instead of retrofitting it later."""
    template = _parse(_payload(questions=[_question(evidence_required=[])]))
    assert template.questions[0].evidence_required == ()

    missing = _question()
    del missing["evidence_required"]
    with pytest.raises(KnowledgeTemplateError, match="evidence_required"):
        _parse(_payload(questions=[missing]))


def test_why_we_ask_can_never_reach_the_customer():
    """It is a reviewer's note. Omitted structurally, not by a convention someone forgets."""
    question = _parse(_payload()).questions[0]
    assert "why_we_ask" in question.as_dict()
    assert "why_we_ask" not in question.as_customer_dict()
    assert "references" not in question.as_customer_dict()


# --- translations are a separate source of truth -----------------------------------------------


def test_arabic_cannot_be_stored_as_a_translation():
    """One source of truth. The canonical text lives on the question; storing it again as a
    translation is the second copy that later drifts."""
    with pytest.raises(KnowledgeTemplateError, match="canonical language"):
        QuestionTranslation("fal_license", "ar", "نص ثانٍ")


def test_a_translation_is_unusable_until_published():
    translation = QuestionTranslation("fal_license", "en", "Do you hold a valid FAL licence?")
    assert translation.is_usable is False
    reviewed = translation.with_status(TranslationStatus.REVIEWED)
    assert reviewed.is_usable is False
    assert reviewed.with_status(TranslationStatus.PUBLISHED).is_usable is True


def test_a_translation_cannot_skip_review():
    translation = QuestionTranslation("fal_license", "en", "…")
    with pytest.raises(IllegalTransitionError, match="cannot move a translation"):
        translation.with_status(TranslationStatus.PUBLISHED)


def test_translation_coverage_counts_only_PUBLISHED():
    """An unreviewed string is not coverage — counting it is how a language nobody on the team
    reads reaches a customer unchecked."""
    template = _parse(_payload(questions=[_question(), _question(id="rega_registration")]))
    generated = QuestionTranslation("fal_license", "en", "FAL?")
    published = generated.with_status(TranslationStatus.REVIEWED).with_status(
        TranslationStatus.PUBLISHED
    )
    assert translation_coverage(template, (generated,), "en") == (0, 2)
    assert translation_coverage(template, (published,), "en") == (1, 2)


def test_the_canonical_language_is_always_fully_covered():
    template = _parse(_payload())
    assert translation_coverage(template, (), CANONICAL_LANGUAGE) == (1, 1)


# --- three concepts, kept apart ---------------------------------------------------------------


def test_an_industry_carries_no_logic():
    """The pull towards parent_industry / aliases / regulatory_family is what turns a lookup value
    into the axis of the system. An industry exists to be chosen from."""
    industry = Industry(slug="real_estate", canonical_name_ar="عقارات")
    assert set(industry.as_dict()) == {"slug", "canonical_name_ar", "status"}
    assert industry.is_selectable is True
    assert Industry("x", "س", IndustryStatus.RETIRED).is_selectable is False


def test_a_template_is_identified_by_industry_AND_version():
    """`real_estate@v3` is what an interview cites forever — readable on its own, and enough to
    explain a report years later."""
    template = _parse(_payload())
    assert template.version_id == "real_estate@v1"


def test_publishing_stamps_when_the_asset_started_affecting_organizations():
    template = (
        _parse(_payload())
        .with_status(TemplateStatus.NEEDS_REVIEW)
        .with_status(TemplateStatus.APPROVED, actor="r@example.com", at=100.0)
    )
    assert template.published_at is None
    published = template.with_status(TemplateStatus.PUBLISHED, at=200.0)
    assert published.published_at == 200.0
    assert published.approved_at == 100.0, "approval and publication are different moments"


# --- the suggestion is not the decision -------------------------------------------------------


def _published(industry: str, version: int) -> KnowledgeTemplate:
    template = parse_generated_template(
        _payload(), industry_slug=industry, version=version,
        prompt_version="v1", generated_by="claude-sonnet-5",
    )
    return (
        template.with_status(TemplateStatus.NEEDS_REVIEW)
        .with_status(TemplateStatus.APPROVED, actor="r@example.com", at=1.0)
        .with_status(TemplateStatus.PUBLISHED, at=2.0)
    )


def test_the_newest_PUBLISHED_template_is_suggested():
    published = (_published("real_estate", 1), _published("real_estate", 3))
    assert suggest_template("real_estate", published).version_id == "real_estate@v3"


def test_an_unpublished_template_is_never_suggested():
    """Review exists precisely so unpublished knowledge cannot reach a customer."""
    draft = _parse(_payload())
    assert suggest_template("real_estate", (draft,)) is None


def test_no_match_suggests_NOTHING_rather_than_something_close():
    """A near-miss template is worse than none: the reviewer would be shown sector questions
    written for someone else and invited to accept them."""
    assert suggest_template("healthcare", (_published("real_estate", 1),)) is None


def test_keeping_the_suggestion_is_recorded_as_not_overridden():
    selection = TemplateSelection("real_estate", ("real_estate@v3",))
    assert selection.was_overridden is False


def test_reality_is_not_one_sector():
    """A brokerage that also builds; a holding company that is neither of its subsidiaries."""
    both = TemplateSelection("real_estate", ("real_estate@v3", "construction@v1"))
    other = TemplateSelection("real_estate", ("holding@v1",))
    assert both.was_overridden is True
    assert other.was_overridden is True


def test_an_interview_must_cite_at_least_one_template_version():
    with pytest.raises(KnowledgeTemplateError, match="at least one template version"):
        TemplateSelection("real_estate", ())


def test_the_same_template_cannot_be_selected_twice():
    with pytest.raises(KnowledgeTemplateError, match="duplicate template version"):
        TemplateSelection("real_estate", ("real_estate@v3", "real_estate@v3"))


def test_answers_cite_the_template_VERSION_not_the_sector():
    """When v4 publishes, this set must still identify the questions that were actually asked."""
    answers = SectorAnswerSet(template_version_id="real_estate@v3")
    assert "template_version_id" in answers.as_dict()
    assert "sector" not in answers.as_dict()
