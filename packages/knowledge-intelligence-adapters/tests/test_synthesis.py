"""Unit tests for the LLM synthesis Tool and its KnowledgeExtractorPort adapter: a valid
answer, Tool Registry audit logging, rejection of malformed LLM output, and the "excerpt
does not address the question" (confidence 0) not-grounded path (CLAUDE.md §19, §22)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from grc_knowledge_intelligence import (
    KnowledgeDomain,
    KnowledgeExtractionError,
    KnowledgeQuestion,
    SourceExcerpt,
    TrustedSource,
    TrustedSourceType,
)
from grc_knowledge_intelligence_adapters import (
    LlmKnowledgeExtractor,
    SynthesizeKnowledgeAnswerTool,
)
from grc_llm import FakeChatModel
from grc_tools import (
    ToolCaller,
    ToolContext,
    ToolInvocationRecord,
    ToolInvocationRecorder,
    ToolRegistry,
)

_VALID_RESPONSE = (
    '{"answer": "Vendor contracts should include audit rights, data protection, and exit '
    'clauses.", "applicable_context": "Any vendor contract involving data processing.", '
    '"confidence": 0.85}'
)
_NOT_GROUNDED_RESPONSE = (
    '{"answer": "The excerpt does not address this question.", '
    '"applicable_context": "n/a", "confidence": 0.0}'
)
_MALFORMED_RESPONSE = '{"answer": "", "applicable_context": "ctx", "confidence": 0.5}'
_OUT_OF_RANGE_RESPONSE = '{"answer": "An answer.", "applicable_context": "ctx", "confidence": 1.5}'


class RecordingRecorder(ToolInvocationRecorder):
    def __init__(self) -> None:
        self.entries: list[ToolInvocationRecord] = []

    async def record(self, entry: ToolInvocationRecord) -> None:
        self.entries.append(entry)


def _context() -> ToolContext:
    return ToolContext(
        caller=ToolCaller.TEST,
        tenant_id=None,  # platform-scope: GRC knowledge is shared reference data
        user_id="dev-user",
        roles=frozenset({"knowledge_intelligence"}),
        agent="knowledge_discovery_engine",
    )


_QUESTION = KnowledgeQuestion(
    question_id="vendor_management.contract_clauses",
    question="What clauses should exist in a vendor contract?",
    domain=KnowledgeDomain.VENDOR_MANAGEMENT,
    category="contract_requirements",
)

_EXCERPT = SourceExcerpt(
    source=TrustedSource(
        source_id="sa-sama",
        name="Saudi Central Bank (SAMA)",
        source_type=TrustedSourceType.GOVERNMENT_REGULATOR,
        url="https://www.sama.gov.sa",
        jurisdiction="SA",
    ),
    text="Vendor contracts must include audit rights, data protection clauses, and exit terms.",
    fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
)


async def test_valid_synthesis_is_returned_and_audited() -> None:
    chat = FakeChatModel(responses=[_VALID_RESPONSE])
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(SynthesizeKnowledgeAnswerTool(chat))
    extractor = LlmKnowledgeExtractor(registry, context=_context())

    answer = await extractor.extract(_QUESTION, _EXCERPT)

    assert "audit rights" in answer.answer
    assert answer.applicable_context == "Any vendor contract involving data processing."
    assert answer.confidence == 0.85
    assert len(recorder.entries) == 1
    assert recorder.entries[0].status.value == "succeeded"
    assert recorder.entries[0].requires_human_approval is False  # read-only, never gated
    assert recorder.entries[0].confidence == 0.85


async def test_not_grounded_excerpt_raises_extraction_error() -> None:
    chat = FakeChatModel(responses=[_NOT_GROUNDED_RESPONSE])
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(SynthesizeKnowledgeAnswerTool(chat))
    extractor = LlmKnowledgeExtractor(registry, context=_context())

    with pytest.raises(KnowledgeExtractionError):
        await extractor.extract(_QUESTION, _EXCERPT)


async def test_empty_answer_is_rejected_and_audited_as_failed() -> None:
    chat = FakeChatModel(responses=[_MALFORMED_RESPONSE])
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(SynthesizeKnowledgeAnswerTool(chat))
    extractor = LlmKnowledgeExtractor(registry, context=_context())

    with pytest.raises(KnowledgeExtractionError):
        await extractor.extract(_QUESTION, _EXCERPT)

    assert recorder.entries[0].status.value == "failed"


async def test_out_of_range_confidence_is_rejected() -> None:
    chat = FakeChatModel(responses=[_OUT_OF_RANGE_RESPONSE])
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(SynthesizeKnowledgeAnswerTool(chat))
    extractor = LlmKnowledgeExtractor(registry, context=_context())

    with pytest.raises(KnowledgeExtractionError):
        await extractor.extract(_QUESTION, _EXCERPT)


async def test_non_json_response_is_rejected() -> None:
    chat = FakeChatModel(responses=["not json at all"])
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(SynthesizeKnowledgeAnswerTool(chat))
    extractor = LlmKnowledgeExtractor(registry, context=_context())

    with pytest.raises(KnowledgeExtractionError):
        await extractor.extract(_QUESTION, _EXCERPT)


async def test_missing_permission_is_denied_and_audited() -> None:
    chat = FakeChatModel(responses=[_VALID_RESPONSE])
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(SynthesizeKnowledgeAnswerTool(chat))
    no_permission_context = ToolContext(
        caller=ToolCaller.TEST, tenant_id=None, user_id="dev-user", roles=frozenset()
    )

    with pytest.raises(KnowledgeExtractionError):
        await LlmKnowledgeExtractor(registry, context=no_permission_context).extract(
            _QUESTION, _EXCERPT
        )

    assert recorder.entries[0].status.value == "denied"
