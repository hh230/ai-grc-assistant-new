"""The Answer Validation Engine across every check it makes — and its two hard promises:
it never mutates the answer, and warnings never fail an answer."""

from __future__ import annotations

import pytest

from answer_validation import (
    AnswerValidator,
    ValidationCode,
    ValidationStatus,
)

from tests.conftest import make_answer, make_context, make_contract


@pytest.fixture
def validator() -> AnswerValidator:
    return AnswerValidator()


def codes(validated) -> set[ValidationCode]:
    return {i.code for i in validated.issues}


# ── the happy path ────────────────────────────────────────────────────────────
def test_well_grounded_answer_passes(validator):
    answer = make_answer("The regulation requires X [S1] and Y [S2].\n\nCitations:\n[S1] ...\n[S2] ...")
    result = validator.validate(answer, context=make_context(2), contract=make_contract())
    assert result.status is ValidationStatus.PASSED
    assert result.is_valid
    assert result.issues == ()
    assert result.confidence_adjustment == 0.0


# ── empty answer ──────────────────────────────────────────────────────────────
def test_empty_answer_fails(validator):
    result = validator.validate(make_answer("   \n  "), context=make_context(2), contract=make_contract())
    assert result.status is ValidationStatus.FAILED
    assert codes(result) == {ValidationCode.EMPTY_ANSWER}


def test_empty_answer_short_circuits_other_checks(validator):
    # no citation/section noise piled on top of an empty answer
    result = validator.validate(make_answer(""), context=make_context(3),
                                contract=make_contract(required_confidence=True,
                                                       required_sections=("Summary",)))
    assert codes(result) == {ValidationCode.EMPTY_ANSWER}


# ── missing citations ─────────────────────────────────────────────────────────
def test_missing_citations_when_required_and_evidence_existed(validator):
    result = validator.validate(make_answer("The regulation requires diligence."),
                                context=make_context(2), contract=make_contract())
    assert result.status is ValidationStatus.FAILED
    assert ValidationCode.MISSING_CITATIONS in codes(result)
    assert result.confidence_adjustment == pytest.approx(-0.5)


def test_no_missing_citations_when_no_evidence_to_cite(validator):
    # insufficient-evidence path: nothing retrieved → not citing is correct, not an error
    result = validator.validate(make_answer("There is insufficient evidence to answer."),
                                context=make_context(0), contract=make_contract())
    assert result.status is ValidationStatus.PASSED


def test_no_missing_citations_when_contract_does_not_require_them(validator):
    result = validator.validate(make_answer("A conversational reply."),
                                context=make_context(2),
                                contract=make_contract(required_citations=False))
    assert result.status is ValidationStatus.PASSED


# ── unknown citation (fabricated) ─────────────────────────────────────────────
def test_citation_outside_context_is_unknown(validator):
    answer = make_answer("Per the rule [S5], you must comply.")
    result = validator.validate(answer, context=make_context(2), contract=make_contract())
    assert result.status is ValidationStatus.FAILED
    assert ValidationCode.UNKNOWN_CITATION in codes(result)
    assert result.errors[0].detail == "S5"


def test_citation_with_empty_context_is_unknown(validator):
    result = validator.validate(make_answer("As stated [S1]."),
                                context=None, contract=make_contract())
    assert ValidationCode.UNKNOWN_CITATION in codes(result)


def test_unknown_citation_penalizes_confidence(validator):
    result = validator.validate(make_answer("See [S3] and [S4]."),
                                context=make_context(2), contract=make_contract())
    # two unknown citations → -0.3 each
    assert result.confidence_adjustment == pytest.approx(-0.6)


# ── malformed citation ────────────────────────────────────────────────────────
def test_malformed_citation_is_a_warning(validator):
    answer = make_answer("Grounded [S1] but also [S] and [Sfoo].")
    result = validator.validate(answer, context=make_context(2), contract=make_contract())
    assert result.status is ValidationStatus.WARNINGS  # warning, not failure
    assert ValidationCode.MALFORMED_CITATION in codes(result)
    details = {i.detail for i in result.warnings}
    assert "[S]" in details and "[Sfoo]" in details


# ── confidence ────────────────────────────────────────────────────────────────
def test_missing_confidence_when_required(validator):
    result = validator.validate(make_answer("Answer [S1]."),
                                context=make_context(1),
                                contract=make_contract(required_confidence=True))
    assert result.status is ValidationStatus.WARNINGS
    assert ValidationCode.MISSING_CONFIDENCE in codes(result)


def test_valid_confidence_passes(validator):
    answer = make_answer("Answer [S1].\n\nConfidence: high — the sources are directly on point.")
    result = validator.validate(answer, context=make_context(1),
                                contract=make_contract(required_confidence=True))
    assert result.status is ValidationStatus.PASSED


def test_unsupported_confidence_value(validator):
    answer = make_answer("Answer [S1].\n\nConfidence: certain")
    result = validator.validate(answer, context=make_context(1),
                                contract=make_contract(required_confidence=True))
    assert ValidationCode.UNSUPPORTED_CONFIDENCE in codes(result)
    assert result.warnings[0].detail == "certain"


def test_confidence_word_without_colon_is_accepted(validator):
    answer = make_answer("Answer [S1]. My confidence here is medium given the evidence.")
    result = validator.validate(answer, context=make_context(1),
                                contract=make_contract(required_confidence=True))
    assert result.status is ValidationStatus.PASSED


# ── required sections ─────────────────────────────────────────────────────────
def test_missing_required_section(validator):
    answer = make_answer("## Findings\nGrounded [S1].")
    result = validator.validate(
        answer, context=make_context(1),
        contract=make_contract(required_sections=("Findings", "Recommendations")),
    )
    assert result.status is ValidationStatus.WARNINGS
    missing = {i.detail for i in result.warnings if i.code is ValidationCode.MISSING_SECTION}
    assert missing == {"Recommendations"}


def test_all_sections_present(validator):
    answer = make_answer("## Findings\nGrounded [S1].\n## Recommendations\nDo X.")
    result = validator.validate(
        answer, context=make_context(1),
        contract=make_contract(required_sections=("Findings", "Recommendations")),
    )
    assert result.status is ValidationStatus.PASSED


# ── invariants ────────────────────────────────────────────────────────────────
def test_validator_never_mutates_the_answer(validator):
    answer = make_answer("Bad answer citing [S9].")
    before = answer.text
    result = validator.validate(answer, context=make_context(1), contract=make_contract())
    assert result.answer is answer          # same object, not a copy
    assert result.answer.text == before     # untouched


def test_validation_without_contract_still_flags_fabricated_and_empty(validator):
    fabricated = validator.validate(make_answer("Per [S9]."), context=make_context(1), contract=None)
    assert ValidationCode.UNKNOWN_CITATION in codes(fabricated)
    empty = validator.validate(make_answer(""), context=make_context(1), contract=None)
    assert empty.status is ValidationStatus.FAILED


def test_to_dict_is_plain_and_serializable(validator):
    import json
    result = validator.validate(make_answer("See [S9]."), context=make_context(1), contract=make_contract())
    data = result.to_dict()
    assert data["status"] == "failed"
    assert data["is_valid"] is False
    assert data["errors"]
    json.dumps(data)


def test_confidence_adjustment_is_floored(validator):
    # many unknown citations must not drive the adjustment below the floor (-1.0)
    text = " ".join(f"[S{n}]" for n in range(10, 25))
    result = validator.validate(make_answer(text), context=make_context(1), contract=make_contract())
    assert result.confidence_adjustment == pytest.approx(-1.0)
