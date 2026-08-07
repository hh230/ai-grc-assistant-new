"""The boundary where the model's output stops being trusted (ADR 0067).

`ClaudeQuestionGenerator` is the one place a model writes something that thousands of customers will
be asked. These tests are about what it REFUSES: anything that would let the model decide instead of
write, and anything malformed enough that a reviewer could not tell what they were approving.

No network and no SDK — the provider is a port, and a stub answers it.
"""

from __future__ import annotations

import json

import pytest
from pipeline_contracts import Answer

from grc_api.knowledge_generation import (
    KNOWLEDGE_PROMPT_VERSION,
    ClaudeQuestionGenerator,
    GeneratedKnowledgeRejected,
)


def _question(**overrides):
    question = {
        "question_id": "fal_license",
        "canonical_text_ar": "هل لديكم رخصة فال سارية؟",
        "type": "boolean",
        "options": [],
        "required": True,
        "category": "licensing",
        "importance": "critical",
        "references": [{"framework": "REGA", "clause": "FAL"}],
        "why_we_ask": "Determines whether the organization may broker at all.",
        "evidence_required": ["License number"],
    }
    question.update(overrides)
    return question


class _Provider:
    """A `GenerationProvider` that answers with whatever text a test hands it."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.requests: list = []

    def generate(self, request):
        self.requests.append(request)
        return Answer(text=self.text, provider="claude", model="claude-sonnet-5")


def _generate(questions=None, *, text=None):
    body = text if text is not None else json.dumps({"questions": questions}, ensure_ascii=False)
    provider = _Provider(body)
    return ClaudeQuestionGenerator(provider, prompt="PROMPT"), provider


def test_a_valid_response_becomes_questions():
    generator, provider = _generate([_question(question_id=f"q_{i}") for i in range(8)])
    questions = generator.generate(industry_slug="real_estate")
    assert len(questions) == 8
    assert questions[0]["canonical_text_ar"].startswith("هل")
    assert questions[0]["references"] == [{"framework": "REGA", "clause": "FAL"}]


def test_no_customer_data_reaches_the_model():
    """Generation happens once per SECTOR. The request carries a slug and nothing else — which is
    the whole reason a customer's answers never travel to a model on this path."""
    generator, provider = _generate([_question(question_id=f"q_{i}") for i in range(8)])
    generator.generate(industry_slug="real_estate")
    user = [s for s in provider.requests[0].segments if s.role.value == "user"]
    assert len(user) == 1
    assert user[0].content == "القطاع: real_estate"


def test_the_prompt_version_is_recorded_on_the_request():
    generator, provider = _generate([_question(question_id=f"q_{i}") for i in range(8)])
    generator.generate(industry_slug="real_estate")
    workflow = next(s for s in provider.requests[0].segments if s.kind.value == "workflow")
    assert workflow.source == KNOWLEDGE_PROMPT_VERSION


@pytest.mark.parametrize(
    "field",
    ["maturity_level", "risk_score", "recommended_controls", "compliance_status", "verdict"],
)
def test_a_decision_field_fails_the_WHOLE_response(field):
    """Claude is responsible for the language, not for the truth. The offending field is not
    dropped: silently discarding it would let the prompt drift into asking for it, and nobody would
    notice until a model's opinion was already being shown to customers as an assessment."""
    questions = [_question(question_id=f"q_{i}") for i in range(8)]
    questions[3][field] = "high"
    generator, _ = _generate(questions)
    with pytest.raises(GeneratedKnowledgeRejected, match="decision fields"):
        generator.generate(industry_slug="real_estate")


def test_an_english_question_is_the_wrong_artifact_not_a_translation_task():
    """Arabic is canonical. A question that arrives in English is not something to fix downstream —
    translations are a separate, human-reviewed layer."""
    questions = [_question(question_id=f"q_{i}") for i in range(8)]
    questions[0]["canonical_text_ar"] = "Do you hold a valid FAL licence?"
    generator, _ = _generate(questions)
    with pytest.raises(GeneratedKnowledgeRejected, match="not in Arabic"):
        generator.generate(industry_slug="real_estate")


def test_a_choice_question_with_one_option_is_refused():
    questions = [_question(question_id=f"q_{i}") for i in range(8)]
    questions[2].update(type="single_choice", options=["نعم"])
    generator, _ = _generate(questions)
    with pytest.raises(GeneratedKnowledgeRejected, match="fewer than two options"):
        generator.generate(industry_slug="real_estate")


def test_a_repeated_question_id_is_refused():
    questions = [_question(question_id="same") for _ in range(8)]
    generator, _ = _generate(questions)
    with pytest.raises(GeneratedKnowledgeRejected, match="repeats question_id"):
        generator.generate(industry_slug="real_estate")


@pytest.mark.parametrize("count", [0, 3, 40])
def test_too_few_or_too_many_questions_are_refused(count):
    generator, _ = _generate([_question(question_id=f"q_{i}") for i in range(count)])
    with pytest.raises(GeneratedKnowledgeRejected, match="outside the agreed"):
        generator.generate(industry_slug="real_estate")


def test_prose_around_the_json_is_refused_but_a_fenced_block_is_not():
    """A code fence is a formatting habit. Prose is a different answer — and a model that starts
    explaining itself is one whose output nobody validated."""
    payload = json.dumps(
        {"questions": [_question(question_id=f"q_{i}") for i in range(8)]}, ensure_ascii=False
    )
    fenced, _ = _generate(text=f"```json\n{payload}\n```")
    assert len(fenced.generate(industry_slug="real_estate")) == 8

    chatty, _ = _generate(text=f"Here are the questions:\n{payload}")
    with pytest.raises(GeneratedKnowledgeRejected, match="not JSON"):
        chatty.generate(industry_slug="real_estate")


def test_a_blank_clause_is_dropped_rather_than_stored():
    """`clause` is optional precisely so the model is never pushed into inventing a number. An empty
    string stored as a citation is a citation that looks present and is not."""
    questions = [_question(question_id=f"q_{i}") for i in range(8)]
    questions[0]["references"] = [{"framework": "PDPL", "clause": "   "}]
    generator, _ = _generate(questions)
    assert generator.generate(industry_slug="real_estate")[0]["references"] == [
        {"framework": "PDPL"}
    ]


def test_a_reference_with_no_framework_is_refused():
    questions = [_question(question_id=f"q_{i}") for i in range(8)]
    questions[1]["references"] = [{"clause": "3.1"}]
    generator, _ = _generate(questions)
    with pytest.raises(GeneratedKnowledgeRejected, match="no framework"):
        generator.generate(industry_slug="real_estate")


def test_the_shipped_prompt_states_the_boundary_it_relies_on():
    """The validator refuses decision fields, but the prompt has to ask for the right thing in the
    first place — a guard that only ever fires is a prompt nobody fixed."""
    from grc_api.knowledge_generation import _prompt_text

    prompt = _prompt_text()
    assert "اللغة، لا عن الحقيقة" in prompt, "the boundary must be stated to the model, in Arabic"
    assert "JSON" in prompt
