"""Does the model actually WRITE in the organization's language?

Every other test in this package proves the directive reaches the request. None of them prove the
model obeys it, because they all use a fake provider — and the bug that started this was precisely
a request that was correct at every layer and produced English anyway.

So this one calls Claude. It skips without a key rather than failing, the same way the Postgres
fixtures skip without a database: a test that cannot run must say so, not pass quietly.
"""

from __future__ import annotations

import os
import re

import pytest

from governance_plan_tools.prompts import SYSTEM_PROMPT, answer_language_directive

ARABIC = re.compile(r"[؀-ۿ]")
LATIN_WORD = re.compile(r"[A-Za-z]{4,}")


@pytest.fixture(scope="module")
def provider():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("no ANTHROPIC_API_KEY — the real-model check cannot run")
    from grc_api.llm_provider import LLMRole, build_generation_provider

    built = build_generation_provider(LLMRole.GOVERNANCE)
    if built is None:
        pytest.skip("no governance provider configured")
    return built


def _ask(provider, language) -> str:
    from governance_plan_tools.draft_tool import _NO_CITATIONS_CONTRACT
    from pipeline_contracts import LLMRequest, PromptFamily, PromptSegment, SegmentKind, SegmentRole

    request = LLMRequest(
        family=PromptFamily.TOOL,
        workflow="governance_plan_draft",
        language=language,
        segments=[
            PromptSegment(role=SegmentRole.SYSTEM, kind=SegmentKind.IDENTITY, title="System",
                          content=SYSTEM_PROMPT, source="governance_plan.system.v2"),
            PromptSegment(role=SegmentRole.SYSTEM, kind=SegmentKind.POLICIES, title="Language",
                          content=answer_language_directive(language), source="governance_plan.system.v2"),
            PromptSegment(role=SegmentRole.USER, kind=SegmentKind.USER_REQUEST, title="Request",
                          content=("RATIONALE: one sentence on why an 8-person real estate brokerage "
                                   "with no written policies needs a compliance owner.")),
        ],
        response_contract=_NO_CITATIONS_CONTRACT,
        params={"max_output_tokens": 200},
    )
    return provider.generate(request).text


def test_arabic_directive_produces_arabic(provider):
    from pipeline_contracts import Language

    text = _ask(provider, Language.ARABIC)
    assert ARABIC.search(text), f"asked for Arabic, got: {text[:200]}"


def test_english_directive_produces_english(provider):
    from pipeline_contracts import Language

    text = _ask(provider, Language.ENGLISH)
    assert LATIN_WORD.search(text), f"asked for English, got: {text[:200]}"
    assert not ARABIC.search(text), f"asked for English, got Arabic: {text[:200]}"
