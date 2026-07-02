"""Unit tests for the rule-based extraction adapters (one capability each)."""
from __future__ import annotations

import pytest
from grc_domain.extraction import ExtractionCandidate, RawDocumentDescriptor
from grc_domain.knowledge import (
    ContentHash,
    DefinitionPayload,
    DocumentFormat,
    DocumentType,
    KnowledgeObjectType,
    KnowledgeScope,
    NormativeStrength,
    ProvenanceRecord,
    RequirementPayload,
    SectionType,
    StorageLocator,
    StructuralAnchor,
    TextSpan,
)
from grc_domain.shared.identifiers import (
    ExtractionRunId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
)
from grc_domain.shared.value_objects import Confidence
from grc_extraction import (
    DocumentPlan,
    ExtractionContext,
    ExtractionResult,
    LayoutBlock,
    NormalizedDocument,
    ParsedDocument,
    ScoringSignals,
    Segment,
    SegmentRole,
)
from grc_extraction_adapters import (
    DocumentNotAvailableError,
    HeadingSegmenter,
    HeuristicConfidenceScorer,
    InMemoryKnowledgeIngestion,
    InMemoryTextDocumentAdapter,
    KeywordClassifier,
    RuleBasedNormativeExtractor,
    WhitespaceNormalizer,
    default_profile,
)

SCOPE = KnowledgeScope.global_()
VER = KnowledgeSourceVersionId("ver-1")


def context() -> ExtractionContext:
    return ExtractionContext(
        scope=SCOPE,
        source_id=KnowledgeSourceId("src-1"),
        version_id=VER,
        document_type=DocumentType.STANDARD,
        profile=default_profile(),
        language="en",
    )


def raw(uri: str = "mem://doc", fmt: DocumentFormat = DocumentFormat.TXT) -> RawDocumentDescriptor:
    return RawDocumentDescriptor(
        storage_locator=StorageLocator(uri),
        content_hash=ContentHash("sha256", "abc"),
        declared_format=fmt,
        declared_language="en",
    )


# --- document adapter ----------------------------------------------------------------------
async def test_text_adapter_parses_nonempty_lines_into_blocks() -> None:
    adapter = InMemoryTextDocumentAdapter(
        {"mem://doc": "Article 5\n  \nThe controller shall act.\n"}
    )
    parsed = await adapter.parse(raw())
    assert [block.text for block in parsed.blocks] == ["Article 5", "The controller shall act."]
    assert parsed.parser_name == "in-memory-text"


def test_text_adapter_supports_text_formats_only() -> None:
    adapter = InMemoryTextDocumentAdapter({})
    assert adapter.supports(DocumentFormat.TXT) is True
    assert adapter.supports(DocumentFormat.MARKDOWN) is True
    assert adapter.supports(DocumentFormat.PDF) is False


async def test_text_adapter_raises_when_content_is_missing() -> None:
    adapter = InMemoryTextDocumentAdapter({})
    with pytest.raises(DocumentNotAvailableError):
        await adapter.parse(raw("mem://absent"))


# --- normalizer ----------------------------------------------------------------------------
async def test_normalizer_collapses_whitespace_and_tags_language() -> None:
    document = ParsedDocument(
        blocks=(LayoutBlock(text="The    controller   shall act", page_number=1),),
        document_format=DocumentFormat.TXT,
    )
    normalized = await WhitespaceNormalizer().normalize(document, language="en")
    assert normalized.blocks[0].text == "The controller shall act"
    assert normalized.language == "en"


# --- segmenter -----------------------------------------------------------------------------
async def test_segmenter_recovers_anchored_segments_with_roles() -> None:
    document = NormalizedDocument(
        blocks=(
            LayoutBlock(text="Article 5: Security Controls", page_number=1),
            LayoutBlock(text="The controller shall implement controls.", page_number=1),
            LayoutBlock(text="6.1 Records", page_number=1),
            LayoutBlock(text="Keep records.", page_number=1),
        ),
        language="en",
    )
    tree = await HeadingSegmenter().segment(document, profile=default_profile())

    assert len(tree.segments) == 2
    assert tree.segments[0].anchor == StructuralAnchor(SectionType.ARTICLE, "5")
    assert "shall implement controls" in tree.segments[0].text
    assert tree.segments[0].role is SegmentRole.NORMATIVE
    assert tree.segments[1].anchor == StructuralAnchor(SectionType.SECTION, "6.1")


async def test_segmenter_keeps_pre_heading_text_as_preamble() -> None:
    document = NormalizedDocument(
        blocks=(
            LayoutBlock(text="This document defines obligations.", page_number=1),
            LayoutBlock(text="Article 1: Scope", page_number=1),
        ),
        language="en",
    )
    tree = await HeadingSegmenter().segment(document, profile=default_profile())
    assert tree.segments[0].anchor == StructuralAnchor(SectionType.SECTION, "preamble")


# --- classifier ----------------------------------------------------------------------------
async def test_classifier_picks_type_by_keywords() -> None:
    document = NormalizedDocument(
        blocks=(LayoutBlock(text="This ISO standard defines controls.", page_number=1),),
        language="en",
    )
    result = await KeywordClassifier().classify(document)
    assert result.document_type is DocumentType.STANDARD
    assert result.confidence.score > 0.55


async def test_classifier_falls_back_to_default_when_no_keywords() -> None:
    document = NormalizedDocument(
        blocks=(LayoutBlock(text="Lorem ipsum dolor sit amet.", page_number=1),), language="en"
    )
    result = await KeywordClassifier().classify(document)
    assert result.document_type is DocumentType.OTHER
    assert result.confidence.score == pytest.approx(0.3)


# --- extractor -----------------------------------------------------------------------------
async def test_extractor_emits_mandatory_requirement_for_shall() -> None:
    segment = Segment(
        anchor=StructuralAnchor(SectionType.ARTICLE, "5"),
        text="The controller shall implement controls.",
        role=SegmentRole.NORMATIVE,
        text_span=TextSpan(0, 40),
        position=0,
    )
    candidate_set = await RuleBasedNormativeExtractor().extract(segment, context())

    assert len(candidate_set) == 1
    candidate = candidate_set.objects[0]
    assert candidate.object_type is KnowledgeObjectType.REQUIREMENT
    assert candidate.normative_strength is NormativeStrength.MANDATORY
    assert isinstance(candidate.payload, RequirementPayload)
    assert candidate.payload.modal == "shall"
    assert candidate.provenance.anchor == segment.anchor
    assert candidate.stable_key


async def test_extractor_emits_definition_with_quoted_term() -> None:
    segment = Segment(
        anchor=StructuralAnchor(SectionType.ARTICLE, "2"),
        text='"Personal Data" means information about a person.',
        role=SegmentRole.DEFINITION,
        position=0,
    )
    candidate_set = await RuleBasedNormativeExtractor().extract(segment, context())

    assert len(candidate_set) == 1
    candidate = candidate_set.objects[0]
    assert candidate.object_type is KnowledgeObjectType.DEFINITION
    assert isinstance(candidate.payload, DefinitionPayload)
    assert candidate.payload.term == "Personal Data"


async def test_extractor_emits_nothing_without_cues() -> None:
    segment = Segment(
        anchor=StructuralAnchor(SectionType.ARTICLE, "9"),
        text="This section is purely descriptive background.",
        position=0,
    )
    candidate_set = await RuleBasedNormativeExtractor().extract(segment, context())
    assert candidate_set.is_empty


# --- scorer --------------------------------------------------------------------------------
def _candidate() -> ExtractionCandidate:
    return ExtractionCandidate(
        object_type=KnowledgeObjectType.REQUIREMENT,
        stable_key="k",
        verbatim_text="The controller shall act.",
        provenance=ProvenanceRecord(source_version_id=VER),
    )


async def test_scorer_averages_present_signals() -> None:
    signals = ScoringSignals(
        extractor_confidence=Confidence(0.9), classification_confidence=Confidence(0.6)
    )
    assert (await HeuristicConfidenceScorer().score(_candidate(), signals=signals)).score == 0.75


async def test_scorer_returns_neutral_when_no_signals() -> None:
    score = await HeuristicConfidenceScorer().score(_candidate(), signals=ScoringSignals())
    assert score.score == 0.5


# --- reference ingestion -------------------------------------------------------------------
async def test_in_memory_ingestion_assigns_ids_and_dedups() -> None:
    content_hash = ContentHash("sha256", "abc")
    result = ExtractionResult(
        run_id=ExtractionRunId("run-1"),
        scope=SCOPE,
        source_id=KnowledgeSourceId("src-1"),
        version_id=VER,
        documents=(
            DocumentPlan(
                language="en",
                document_format=DocumentFormat.TXT,
                storage_locator=StorageLocator("mem://doc"),
                content_hash=content_hash,
            ),
        ),
        objects=(_candidate(),),
    )
    ingestion = InMemoryKnowledgeIngestion()

    assert await ingestion.find_existing(SCOPE, content_hash) is None
    outcome = await ingestion.persist_result(result)
    assert len(outcome.object_ids) == 1
    assert await ingestion.find_existing(SCOPE, content_hash) is not None
    assert len(ingestion.persisted) == 1
