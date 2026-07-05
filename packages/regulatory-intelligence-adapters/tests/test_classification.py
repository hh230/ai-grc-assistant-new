"""Unit tests for the LLM classifier Tool and its ObligationClassifierPort adapter: valid
classification, Tool Registry audit logging, and rejection of malformed/unsupported LLM
output (CLAUDE.md §19, §22)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from grc_domain.platform import Permission
from grc_llm import FakeChatModel
from grc_regulatory_intelligence import (
    ClassificationStatus,
    ObligationCandidate,
    ObligationClassificationError,
    RawRegulatoryDocument,
    RegulatoryIntelligenceEngine,
)
from grc_regulatory_intelligence_adapters import (
    CLASSIFY_REGULATORY_OBLIGATION_VERSION,
    ClassifyRegulatoryObligationTool,
    LlmObligationClassifier,
    RuleBasedObligationExtractor,
)
from grc_tools import (
    ToolCaller,
    ToolContext,
    ToolInvocationRecord,
    ToolInvocationRecorder,
    ToolRegistry,
)

_VALID_RESPONSE = (
    '{"obligation_type": "requirement", "control_domain": "data_protection", '
    '"suggested_policy_title": "Data Encryption Policy", "severity": "high", "confidence": 0.87}'
)


class RecordingRecorder(ToolInvocationRecorder):
    def __init__(self) -> None:
        self.entries: list[ToolInvocationRecord] = []

    async def record(self, entry: ToolInvocationRecord) -> None:
        self.entries.append(entry)


def _context() -> ToolContext:
    return ToolContext(
        caller=ToolCaller.TEST,
        tenant_id=None,  # platform-scope: regulatory obligations are shared reference data
        user_id="dev-user",
        roles=frozenset({"regulatory_intelligence"}),
        agent="regulatory_intelligence_engine",
    )


def _document() -> RawRegulatoryDocument:
    return RawRegulatoryDocument(
        source_id="src-nca-ecc",
        url="https://example.gov/nca-ecc",
        fetched_at=datetime(2026, 7, 5, tzinfo=timezone.utc),
        content_hash="hash",
        raw_text="1. Entities shall encrypt data at rest and in transit.",
    )


def _candidate() -> ObligationCandidate:
    return ObligationCandidate(
        obligation_text="Entities shall encrypt data at rest and in transit.",
        source_char_start=3,
        source_char_end=56,
    )


async def test_valid_classification_is_returned_and_audited() -> None:
    chat = FakeChatModel(responses=[_VALID_RESPONSE])
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(ClassifyRegulatoryObligationTool(chat))
    classifier = LlmObligationClassifier(registry, context=_context())

    classification = await classifier.classify(_candidate(), document=_document())

    assert classification.obligation_type.value == "requirement"
    assert classification.control_domain.value == "data_protection"
    assert classification.severity.value == "high"
    assert classification.confidence == 0.87
    assert classification.prompt_version == CLASSIFY_REGULATORY_OBLIGATION_VERSION
    assert classification.classifier_model == "fake-chat"

    # Every classifier call is recorded — the audit trail CLAUDE.md §19 requires.
    assert len(recorder.entries) == 1
    entry = recorder.entries[0]
    assert entry.status.value == "succeeded"
    assert entry.tool_name == "classify_regulatory_obligation"
    assert entry.prompt_version == CLASSIFY_REGULATORY_OBLIGATION_VERSION
    assert entry.confidence == 0.87
    assert entry.tenant_id is None


async def test_malformed_json_is_rejected_and_recorded_as_failed() -> None:
    chat = FakeChatModel(responses=["not json at all"])
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(ClassifyRegulatoryObligationTool(chat))
    classifier = LlmObligationClassifier(registry, context=_context())

    with pytest.raises(ObligationClassificationError):
        await classifier.classify(_candidate(), document=_document())

    assert recorder.entries[0].status.value == "failed"


async def test_unsupported_obligation_type_is_rejected() -> None:
    bad_response = (
        '{"obligation_type": "not_a_real_type", "control_domain": "data_protection", '
        '"suggested_policy_title": "x", "severity": "high", "confidence": 0.5}'
    )
    chat = FakeChatModel(responses=[bad_response])
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(ClassifyRegulatoryObligationTool(chat))
    classifier = LlmObligationClassifier(registry, context=_context())

    with pytest.raises(ObligationClassificationError):
        await classifier.classify(_candidate(), document=_document())

    assert recorder.entries[0].status.value == "failed"


async def test_out_of_range_confidence_is_rejected() -> None:
    bad_response = (
        '{"obligation_type": "requirement", "control_domain": "data_protection", '
        '"suggested_policy_title": "x", "severity": "high", "confidence": 1.5}'
    )
    chat = FakeChatModel(responses=[bad_response])
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(ClassifyRegulatoryObligationTool(chat))
    classifier = LlmObligationClassifier(registry, context=_context())

    with pytest.raises(ObligationClassificationError):
        await classifier.classify(_candidate(), document=_document())


async def test_missing_permission_surfaces_as_classification_error() -> None:
    chat = FakeChatModel(responses=[_VALID_RESPONSE])
    registry = ToolRegistry(recorder=RecordingRecorder())
    registry.register(ClassifyRegulatoryObligationTool(chat))
    no_permission_context = ToolContext(
        caller=ToolCaller.TEST, tenant_id=None, user_id="dev-user", roles=frozenset()
    )
    classifier = LlmObligationClassifier(registry, context=no_permission_context)

    with pytest.raises(ObligationClassificationError):
        await classifier.classify(_candidate(), document=_document())


async def test_engine_end_to_end_with_rule_based_extraction_and_llm_classification() -> None:
    """The full PI-P1 pipeline: connector output -> RegulatoryIntelligenceEngine (rule-based
    split + LLM classify) -> pending_review obligations, with every classification audited."""
    document = _document()
    chat = FakeChatModel(responses=[_VALID_RESPONSE])
    recorder = RecordingRecorder()
    registry = ToolRegistry(recorder=recorder)
    registry.register(ClassifyRegulatoryObligationTool(chat))

    engine = RegulatoryIntelligenceEngine(
        extractor=RuleBasedObligationExtractor(),
        classifier=LlmObligationClassifier(registry, context=_context()),
    )

    result = await engine.run(document)

    assert len(result.obligations) == 1
    obligation = result.obligations[0]
    assert obligation.classification_status == ClassificationStatus.PENDING_REVIEW
    assert obligation.classification.obligation_type.value == "requirement"
    assert len(recorder.entries) == 1


def test_tool_requires_the_regulatory_intelligence_permission() -> None:
    tool = ClassifyRegulatoryObligationTool(FakeChatModel())
    assert Permission("regulatory_intelligence") in tool.descriptor.required_permissions
