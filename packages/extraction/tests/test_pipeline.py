"""Unit tests for the extraction pipeline coordinator (the engine core).

These exercise ``ExtractionPipeline`` end to end against in-memory fake ports — no parser, OCR,
LLM, or database — verifying that it drives the ``ExtractionRun`` aggregate through its stages,
checkpoints each stage, routes by confidence, persists through the ingestion port, and fails
**safe** (no partial publication) when a stage errors. This is the Tools-callable, LLM-free
test path the architecture promises (CLAUDE.md §9, §22).
"""
from __future__ import annotations

import itertools

import pytest
from grc_domain.extraction import (
    CandidateRelationship,
    ExtractionCandidate,
    ExtractionRun,
    ExtractionRunStatus,
    ExtractionStage,
    RawDocumentDescriptor,
)
from grc_domain.extraction.enums import StageStatus
from grc_domain.knowledge import (
    ContentHash,
    DocumentFormat,
    DocumentType,
    KnowledgeObjectType,
    KnowledgeScope,
    ProvenanceRecord,
    RelationshipEndpoint,
    RelationshipPredicate,
    SectionType,
    StorageLocator,
    StructuralAnchor,
)
from grc_domain.shared.identifiers import (
    ExtractionRunId,
    FrameworkControlId,
    FrameworkId,
    KnowledgeObjectId,
    KnowledgeRelationshipId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
    StageExecutionId,
)
from grc_domain.shared.value_objects import Confidence
from grc_extraction import (
    CandidateSet,
    ClassificationResult,
    ClassifierPort,
    ConfidenceScorerPort,
    ConfidenceThresholds,
    DocumentAdapterPort,
    ExtractionContext,
    ExtractionPipeline,
    ExtractionProfile,
    ExtractionResult,
    ExtractorDescriptor,
    ExtractorPort,
    ExtractorRef,
    ExtractorRegistry,
    ExtractorTechnique,
    FrameworkMappingPort,
    IngestionResult,
    KnowledgeIngestionPort,
    LayoutBlock,
    NormalizedDocument,
    NormalizerPort,
    OcrPort,
    ParsedDocument,
    PipelineError,
    PipelinePorts,
    ScoringSignals,
    Segment,
    SegmenterPort,
    SegmentTree,
    StageExecutionIdFactory,
)

# --- shared identifiers --------------------------------------------------------------------
SCOPE = KnowledgeScope.global_()
SRC = KnowledgeSourceId("src-1")
VER = KnowledgeSourceVersionId("ver-1")


# --- fake ports (in-memory, deterministic) -------------------------------------------------
class FakeDocumentAdapter(DocumentAdapterPort):
    def __init__(self, parsed: ParsedDocument, *, supported: bool = True) -> None:
        self._parsed = parsed
        self._supported = supported
        self.parse_calls = 0

    def supports(self, document_format: DocumentFormat) -> bool:
        return self._supported

    async def parse(self, document: RawDocumentDescriptor) -> ParsedDocument:
        self.parse_calls += 1
        return self._parsed


class FakeOcr(OcrPort):
    def __init__(self, parsed: ParsedDocument) -> None:
        self._parsed = parsed
        self.recognize_calls = 0

    async def recognize(self, document: RawDocumentDescriptor) -> ParsedDocument:
        self.recognize_calls += 1
        return self._parsed


class FakeNormalizer(NormalizerPort):
    async def normalize(
        self, document: ParsedDocument, *, language: str | None = None
    ) -> NormalizedDocument:
        return NormalizedDocument(blocks=document.blocks, language=language or document.language)


class FakeSegmenter(SegmenterPort):
    def __init__(self, tree: SegmentTree) -> None:
        self._tree = tree

    async def segment(
        self, document: NormalizedDocument, *, profile: ExtractionProfile
    ) -> SegmentTree:
        return self._tree


class FakeClassifier(ClassifierPort):
    def __init__(self, result: ClassificationResult) -> None:
        self._result = result

    async def classify(
        self, document: NormalizedDocument, *, segments: SegmentTree | None = None
    ) -> ClassificationResult:
        return self._result


class FakeExtractor(ExtractorPort):
    def __init__(
        self,
        descriptor: ExtractorDescriptor,
        candidates: tuple[ExtractionCandidate, ...] = (),
        *,
        raises: Exception | None = None,
    ) -> None:
        self._descriptor = descriptor
        self._candidates = candidates
        self._raises = raises

    @property
    def descriptor(self) -> ExtractorDescriptor:
        return self._descriptor

    async def extract(self, segment: Segment, context: ExtractionContext) -> CandidateSet:
        if self._raises is not None:
            raise self._raises
        return CandidateSet(objects=self._candidates)


class FakeScorer(ConfidenceScorerPort):
    def __init__(self, score: float) -> None:
        self._score = score

    async def score(self, candidate: ExtractionCandidate, *, signals: ScoringSignals) -> Confidence:
        return Confidence(self._score)


class FakeFrameworkMapper(FrameworkMappingPort):
    def __init__(self, edge: CandidateRelationship) -> None:
        self._edge = edge
        self.calls = 0

    async def map_candidate(
        self, candidate: ExtractionCandidate, context: ExtractionContext
    ) -> tuple[CandidateRelationship, ...]:
        self.calls += 1
        return (self._edge,)


class FakeIngestion(KnowledgeIngestionPort):
    def __init__(
        self,
        *,
        existing: IngestionResult | None = None,
        result_ids: tuple[KnowledgeObjectId, ...] = (),
    ) -> None:
        self._existing = existing
        self._result_ids = result_ids
        self.persist_calls = 0
        self.persisted: ExtractionResult | None = None

    async def find_existing(
        self, scope: KnowledgeScope, content_hash: ContentHash
    ) -> IngestionResult | None:
        return self._existing

    async def persist_result(self, result: ExtractionResult) -> IngestionResult:
        self.persist_calls += 1
        self.persisted = result
        rel_ids = tuple(
            KnowledgeRelationshipId(f"rel-{index}") for index in range(len(result.relationships))
        )
        return IngestionResult(
            object_ids=self._result_ids, relationship_ids=rel_ids, version_id=result.version_id
        )


# --- builders ------------------------------------------------------------------------------
def raw(document_format: DocumentFormat = DocumentFormat.PDF) -> RawDocumentDescriptor:
    return RawDocumentDescriptor(
        storage_locator=StorageLocator("s3://bucket/raw"),
        content_hash=ContentHash("sha256", "abc"),
        declared_format=document_format,
    )


def make_run(document_format: DocumentFormat = DocumentFormat.PDF) -> ExtractionRun:
    return ExtractionRun.open(
        id=ExtractionRunId("run-1"),
        scope=SCOPE,
        source_id=SRC,
        version_id=VER,
        raw_document=raw(document_format),
        idempotency_key="key-1",
        pipeline_version="1.0.0",
    )


def parsed_doc() -> ParsedDocument:
    return ParsedDocument(
        blocks=(LayoutBlock(text="Article 5 - Controls", page_number=1),),
        document_format=DocumentFormat.PDF,
        language="en",
    )


def segment_tree() -> SegmentTree:
    return SegmentTree(
        (
            Segment(
                anchor=StructuralAnchor(SectionType.ARTICLE, "5"),
                text="The controller shall implement controls.",
                position=0,
            ),
        )
    )


def classification(score: float = 0.9) -> ClassificationResult:
    return ClassificationResult(document_type=DocumentType.STANDARD, confidence=Confidence(score))


def candidate(
    object_type: KnowledgeObjectType = KnowledgeObjectType.DEFINITION, stable_key: str = "k1"
) -> ExtractionCandidate:
    return ExtractionCandidate(
        object_type=object_type,
        stable_key=stable_key,
        verbatim_text="The controller shall implement controls.",
        provenance=ProvenanceRecord(source_version_id=VER),
    )


def descriptor(name: str = "rule-x") -> ExtractorDescriptor:
    return ExtractorDescriptor(
        name=name,
        version="1.0.0",
        technique=ExtractorTechnique.RULE,
        produces=frozenset(
            {
                KnowledgeObjectType.DEFINITION,
                KnowledgeObjectType.CONTROL,
                KnowledgeObjectType.REQUIREMENT,
            }
        ),
    )


def make_profile(discard_below: float = 0.1) -> ExtractionProfile:
    return ExtractionProfile(
        document_type=DocumentType.STANDARD,
        version="1.0.0",
        grammar_ref="grammar:standard",
        extractor_refs=(ExtractorRef("rule-x"),),
        thresholds=ConfidenceThresholds(
            auto_accept_at=0.75, review_below=0.75, discard_below=discard_below
        ),
        default_language="en",
    )


def registry_with(extractor: ExtractorPort) -> ExtractorRegistry:
    registry = ExtractorRegistry()
    registry.register(extractor)
    return registry


def id_factory() -> StageExecutionIdFactory:
    counter = itertools.count(1)

    def _next() -> StageExecutionId:
        return StageExecutionId(f"se-{next(counter)}")

    return _next


def pipeline(ports: PipelinePorts) -> ExtractionPipeline:
    return ExtractionPipeline(ports, new_stage_execution_id=id_factory())


def mapped_edge() -> CandidateRelationship:
    return CandidateRelationship(
        predicate=RelationshipPredicate.MAPPED_TO,
        subject=RelationshipEndpoint.for_object(KnowledgeObjectId("obj-ctrl")),
        target=RelationshipEndpoint.for_framework_control(
            FrameworkId("framework:iso_27001"), FrameworkControlId("A.8.1")
        ),
        provenance=ProvenanceRecord(source_version_id=VER),
    )


# --- happy path ----------------------------------------------------------------------------
async def test_high_confidence_run_completes_and_persists() -> None:
    adapter = FakeDocumentAdapter(parsed_doc())
    ingestion = FakeIngestion(result_ids=(KnowledgeObjectId("obj-1"),))
    ports = PipelinePorts(
        document_adapter=adapter,
        normalizer=FakeNormalizer(),
        segmenter=FakeSegmenter(segment_tree()),
        classifier=FakeClassifier(classification()),
        extractors=registry_with(FakeExtractor(descriptor(), (candidate(),))),
        scorer=FakeScorer(0.9),
        ingestion=ingestion,
    )
    run = make_run()

    outcome = await pipeline(ports).run(run, profile=make_profile())

    assert run.status is ExtractionRunStatus.COMPLETED
    assert outcome.final_status is ExtractionRunStatus.COMPLETED
    assert outcome.deduplicated is False
    assert run.produced_object_ids == (KnowledgeObjectId("obj-1"),)
    assert ingestion.persist_calls == 1
    assert ingestion.persisted is not None
    assert len(ingestion.persisted.objects) == 1
    assert ingestion.persisted.objects[0].confidence == Confidence(0.9)


async def test_all_pipeline_stages_are_checkpointed_in_order() -> None:
    ports = _default_ports()
    run = make_run()

    await pipeline(ports).run(run, profile=make_profile())

    stages = [execution.stage for execution in run.stage_executions]
    assert stages == [
        ExtractionStage.INTAKE,
        ExtractionStage.PARSE,
        ExtractionStage.NORMALIZE,
        ExtractionStage.SEGMENT,
        ExtractionStage.CLASSIFY,
        ExtractionStage.EXTRACT_OBJECTS,
        ExtractionStage.EXTRACT_RELATIONSHIPS,
        ExtractionStage.SCORE,
        ExtractionStage.PERSIST,
    ]
    assert all(execution.status is StageStatus.SUCCEEDED for execution in run.stage_executions)


# --- confidence routing --------------------------------------------------------------------
async def test_low_confidence_routes_to_human_review() -> None:
    ports = _default_ports(scorer_score=0.5)
    run = make_run()

    outcome = await pipeline(ports).run(run, profile=make_profile())

    assert run.status is ExtractionRunStatus.AWAITING_REVIEW
    assert outcome.final_status is ExtractionRunStatus.AWAITING_REVIEW


async def test_candidates_at_or_below_discard_threshold_are_dropped() -> None:
    ingestion = FakeIngestion(result_ids=())
    ports = _default_ports(scorer_score=0.05, ingestion=ingestion)  # 0.05 <= discard_below 0.1
    run = make_run()

    await pipeline(ports).run(run, profile=make_profile(discard_below=0.1))

    assert run.status is ExtractionRunStatus.COMPLETED  # nothing survived to need review
    assert ingestion.persisted is not None
    assert ingestion.persisted.objects == ()


# --- idempotency ---------------------------------------------------------------------------
async def test_existing_content_short_circuits_without_reprocessing() -> None:
    adapter = FakeDocumentAdapter(parsed_doc())
    ingestion = FakeIngestion(existing=IngestionResult(object_ids=(KnowledgeObjectId("pre-1"),)))
    ports = PipelinePorts(
        document_adapter=adapter,
        normalizer=FakeNormalizer(),
        segmenter=FakeSegmenter(segment_tree()),
        classifier=FakeClassifier(classification()),
        extractors=registry_with(FakeExtractor(descriptor(), (candidate(),))),
        scorer=FakeScorer(0.9),
        ingestion=ingestion,
    )
    run = make_run()

    outcome = await pipeline(ports).run(run, profile=make_profile())

    assert outcome.deduplicated is True
    assert run.status is ExtractionRunStatus.COMPLETED
    assert run.produced_object_ids == (KnowledgeObjectId("pre-1"),)
    assert adapter.parse_calls == 0
    assert ingestion.persist_calls == 0


# --- fail-safe -----------------------------------------------------------------------------
async def test_extractor_error_fails_run_safe_without_persisting() -> None:
    ingestion = FakeIngestion(result_ids=(KnowledgeObjectId("obj-1"),))
    failing = FakeExtractor(descriptor(), raises=ValueError("boom"))
    ports = PipelinePorts(
        document_adapter=FakeDocumentAdapter(parsed_doc()),
        normalizer=FakeNormalizer(),
        segmenter=FakeSegmenter(segment_tree()),
        classifier=FakeClassifier(classification()),
        extractors=registry_with(failing),
        scorer=FakeScorer(0.9),
        ingestion=ingestion,
    )
    run = make_run()

    with pytest.raises(PipelineError) as exc_info:
        await pipeline(ports).run(run, profile=make_profile())

    assert exc_info.value.error.stage is ExtractionStage.EXTRACT_OBJECTS
    assert run.status is ExtractionRunStatus.FAILED
    assert run.error is not None
    assert run.error.stage is ExtractionStage.EXTRACT_OBJECTS
    assert ingestion.persist_calls == 0
    failed = [e for e in run.stage_executions if e.status is StageStatus.FAILED]
    assert len(failed) == 1
    assert failed[0].stage is ExtractionStage.EXTRACT_OBJECTS


# --- OCR fallback --------------------------------------------------------------------------
async def test_ocr_is_used_when_the_adapter_does_not_support_the_format() -> None:
    adapter = FakeDocumentAdapter(parsed_doc(), supported=False)
    ocr = FakeOcr(parsed_doc())
    ports = PipelinePorts(
        document_adapter=adapter,
        normalizer=FakeNormalizer(),
        segmenter=FakeSegmenter(segment_tree()),
        classifier=FakeClassifier(classification()),
        extractors=registry_with(FakeExtractor(descriptor(), (candidate(),))),
        scorer=FakeScorer(0.9),
        ingestion=FakeIngestion(result_ids=(KnowledgeObjectId("obj-1"),)),
        ocr=ocr,
    )
    run = make_run()

    await pipeline(ports).run(run, profile=make_profile())

    assert ocr.recognize_calls == 1
    assert adapter.parse_calls == 0
    assert run.status is ExtractionRunStatus.COMPLETED


async def test_unsupported_format_without_ocr_fails_run() -> None:
    ingestion = FakeIngestion(result_ids=(KnowledgeObjectId("obj-1"),))
    ports = PipelinePorts(
        document_adapter=FakeDocumentAdapter(parsed_doc(), supported=False),
        normalizer=FakeNormalizer(),
        segmenter=FakeSegmenter(segment_tree()),
        classifier=FakeClassifier(classification()),
        extractors=registry_with(FakeExtractor(descriptor(), (candidate(),))),
        scorer=FakeScorer(0.9),
        ingestion=ingestion,
    )
    run = make_run()

    with pytest.raises(PipelineError) as exc_info:
        await pipeline(ports).run(run, profile=make_profile())

    assert exc_info.value.error.code == "unsupported_format"
    assert run.status is ExtractionRunStatus.FAILED
    assert ingestion.persist_calls == 0


# --- framework mapping ---------------------------------------------------------------------
async def test_control_candidates_are_offered_to_the_framework_mapper() -> None:
    mapper = FakeFrameworkMapper(mapped_edge())
    ports = PipelinePorts(
        document_adapter=FakeDocumentAdapter(parsed_doc()),
        normalizer=FakeNormalizer(),
        segmenter=FakeSegmenter(segment_tree()),
        classifier=FakeClassifier(classification()),
        extractors=registry_with(
            FakeExtractor(descriptor(), (candidate(KnowledgeObjectType.CONTROL, "ctrl-1"),))
        ),
        scorer=FakeScorer(0.9),
        ingestion=FakeIngestion(result_ids=(KnowledgeObjectId("obj-1"),)),
        framework_mapper=mapper,
    )
    run = make_run()

    outcome = await pipeline(ports).run(run, profile=make_profile())

    assert mapper.calls == 1
    assert len(outcome.result.relationships) == 1
    assert outcome.result.relationships[0].predicate is RelationshipPredicate.MAPPED_TO


async def test_definition_candidates_are_not_mapped() -> None:
    mapper = FakeFrameworkMapper(mapped_edge())
    ports = _default_ports(framework_mapper=mapper)  # default candidate is a DEFINITION
    run = make_run()

    outcome = await pipeline(ports).run(run, profile=make_profile())

    assert mapper.calls == 0
    assert outcome.result.relationships == ()


# --- helpers -------------------------------------------------------------------------------
def _default_ports(
    *,
    scorer_score: float = 0.9,
    ingestion: FakeIngestion | None = None,
    framework_mapper: FrameworkMappingPort | None = None,
) -> PipelinePorts:
    return PipelinePorts(
        document_adapter=FakeDocumentAdapter(parsed_doc()),
        normalizer=FakeNormalizer(),
        segmenter=FakeSegmenter(segment_tree()),
        classifier=FakeClassifier(classification()),
        extractors=registry_with(FakeExtractor(descriptor(), (candidate(),))),
        scorer=FakeScorer(scorer_score),
        ingestion=(
            ingestion
            if ingestion is not None
            else FakeIngestion(result_ids=(KnowledgeObjectId("obj-1"),))
        ),
        framework_mapper=framework_mapper,
    )
