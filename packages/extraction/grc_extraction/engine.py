"""The extraction pipeline coordinator — the engine core (pure orchestration).

This is the heart of the Knowledge Extraction Engine. Given an opened ``ExtractionRun`` and a
bundle of resolved ports, ``ExtractionPipeline`` drives the run through its ordered stages
(intake → parse → normalize → segment → classify → extract objects → extract relationships →
score → persist), recording a durable ``StageExecution`` checkpoint per stage and finalizing
the run **fail-safe**: any stage error fails the run with no partial publication, leaving it
resumable.

The coordinator depends only on the ports, the working artifacts, and the ``grc_domain`` model
— never on a document parser, OCR, an LLM, or a database. Concrete adapters that implement the
ports live in outer infrastructure packages, so AI- or library-backed processing can plug in
later without touching this orchestration. (CLAUDE.md §7, §12; Handbook §8 milestone 6.)
"""
from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass, replace
from typing import Protocol, TypeVar

from grc_domain.extraction import (
    CandidateRelationship,
    ExtractionCandidate,
    ExtractionError,
    ExtractionRun,
    ExtractionRunStatus,
    ExtractionStage,
)
from grc_domain.knowledge import KnowledgeObjectType
from grc_domain.shared.identifiers import ExtractionRunId, StageExecutionId

from .artifacts import (
    ClassificationResult,
    DocumentPlan,
    ExtractionContext,
    ExtractionResult,
    IngestionResult,
    ScoringSignals,
    SectionPlan,
    SegmentTree,
)
from .exceptions import PipelineError
from .ports import (
    ClassifierPort,
    ConfidenceScorerPort,
    DocumentAdapterPort,
    FrameworkMappingPort,
    KnowledgeIngestionPort,
    NormalizerPort,
    OcrPort,
    RelationshipExtractorPort,
    SegmenterPort,
)
from .profiles import ExtractionProfile
from .registry import ExtractorRegistry

_T = TypeVar("_T")

# Only normative candidates are offered to the Framework Engine for cross-mapping; descriptive
# objects (definitions, references, …) are not mapped to controls.
_MAPPABLE_OBJECT_TYPES: frozenset[KnowledgeObjectType] = frozenset(
    {KnowledgeObjectType.CONTROL, KnowledgeObjectType.REQUIREMENT}
)


class StageExecutionIdFactory(Protocol):
    """Supplies a unique id per stage attempt (injected so the engine stays deterministic/pure)."""

    def __call__(self) -> StageExecutionId: ...


@dataclass(frozen=True)
class PipelinePorts:
    """The resolved port adapters one pipeline run composes.

    ``document_adapter`` is pre-resolved to one that supports the document's format; ``ocr`` is
    the fallback used when it does not (scanned/image documents). Relationship extraction and
    framework mapping are optional — a profile that needs neither simply omits them.
    """

    document_adapter: DocumentAdapterPort
    normalizer: NormalizerPort
    segmenter: SegmenterPort
    classifier: ClassifierPort
    extractors: ExtractorRegistry
    scorer: ConfidenceScorerPort
    ingestion: KnowledgeIngestionPort
    ocr: OcrPort | None = None
    relationship_extractors: tuple[RelationshipExtractorPort, ...] = ()
    framework_mapper: FrameworkMappingPort | None = None


@dataclass(frozen=True)
class PipelineOutcome:
    """The successful product of a run (the ``ExtractionRun`` itself is mutated in place)."""

    run_id: ExtractionRunId
    final_status: ExtractionRunStatus
    result: ExtractionResult
    ingestion: IngestionResult
    deduplicated: bool = False


class ExtractionPipeline:
    """Drives one ``ExtractionRun`` through its stages via injected ports, fail-safe.

    ``run`` expects a freshly opened (``PENDING``) run; it begins the run, executes each stage
    behind a durable checkpoint, persists the result through the Knowledge ingestion port, and
    finalizes the run to ``COMPLETED`` (all candidates cleared the auto-accept threshold) or
    ``AWAITING_REVIEW`` (some need a human gate). On any stage error the run is left ``FAILED``
    and a ``PipelineError`` is raised — nothing is partially published.
    """

    def __init__(
        self, ports: PipelinePorts, *, new_stage_execution_id: StageExecutionIdFactory
    ) -> None:
        self._ports = ports
        self._new_stage_execution_id = new_stage_execution_id

    async def run(self, run: ExtractionRun, *, profile: ExtractionProfile) -> PipelineOutcome:
        run.begin()

        # --- intake: idempotency check against the Knowledge Database -----------------------
        existing = await self._run_stage(
            run,
            ExtractionStage.INTAKE,
            self._ports.ingestion.find_existing(run.scope, run.raw_document.content_hash),
        )
        if existing is not None:
            run.record_results(
                object_ids=existing.object_ids, relationship_ids=existing.relationship_ids
            )
            run.complete()
            return PipelineOutcome(
                run_id=run.id,
                final_status=run.status,
                result=_empty_result(run),
                ingestion=existing,
                deduplicated=True,
            )

        # --- parse (or OCR for unsupported/scanned formats) --------------------------------
        document_format = run.raw_document.declared_format
        if self._ports.document_adapter.supports(document_format):
            parsed = await self._run_stage(
                run, ExtractionStage.PARSE, self._ports.document_adapter.parse(run.raw_document)
            )
        elif self._ports.ocr is not None:
            parsed = await self._run_stage(
                run, ExtractionStage.PARSE, self._ports.ocr.recognize(run.raw_document)
            )
        else:
            error = ExtractionError(
                stage=ExtractionStage.PARSE,
                code="unsupported_format",
                message=f"No adapter supports {document_format.value} and no OCR fallback",
            )
            run.fail(error=error)
            raise PipelineError(run.id, error)

        # --- normalize ----------------------------------------------------------------------
        language = profile.default_language or parsed.language or run.raw_document.declared_language
        normalized = await self._run_stage(
            run,
            ExtractionStage.NORMALIZE,
            self._ports.normalizer.normalize(parsed, language=language),
        )
        language = profile.default_language or normalized.language or language
        if language is None:
            error = ExtractionError(
                stage=ExtractionStage.NORMALIZE,
                code="missing_language",
                message="Document language could not be determined; cannot persist a manifestation",
            )
            run.fail(error=error)
            raise PipelineError(run.id, error)

        # --- segment & classify -------------------------------------------------------------
        tree = await self._run_stage(
            run, ExtractionStage.SEGMENT, self._ports.segmenter.segment(normalized, profile=profile)
        )
        classification = await self._run_stage(
            run,
            ExtractionStage.CLASSIFY,
            self._ports.classifier.classify(normalized, segments=tree),
        )

        context = ExtractionContext(
            scope=run.scope,
            source_id=run.source_id,
            version_id=run.version_id,
            document_type=profile.document_type,
            profile=profile,
            language=language,
        )

        # --- extract objects, then relationships -------------------------------------------
        candidates = await self._run_stage(
            run, ExtractionStage.EXTRACT_OBJECTS, self._extract_objects(tree, context)
        )
        relationships = await self._run_stage(
            run,
            ExtractionStage.EXTRACT_RELATIONSHIPS,
            self._extract_relationships(candidates, context),
        )

        # --- score & route by confidence ----------------------------------------------------
        scored = await self._run_stage(
            run, ExtractionStage.SCORE, self._score(candidates, classification)
        )
        thresholds = profile.thresholds
        surviving = tuple(
            candidate
            for candidate in scored
            if candidate.confidence is None or candidate.confidence.score > thresholds.discard_below
        )
        needs_review = any(
            candidate.confidence is not None
            and candidate.confidence.score < thresholds.auto_accept_at
            for candidate in surviving
        )

        # --- persist atomically through the Unit of Work + outbox (behind the port) --------
        result = ExtractionResult(
            run_id=run.id,
            scope=run.scope,
            source_id=run.source_id,
            version_id=run.version_id,
            documents=(self._document_plan(run, tree, language),),
            objects=surviving,
            relationships=relationships,
            pipeline_version=run.pipeline_version,
        )
        ingestion = await self._run_stage(
            run, ExtractionStage.PERSIST, self._ports.ingestion.persist_result(result)
        )
        run.record_results(
            object_ids=ingestion.object_ids, relationship_ids=ingestion.relationship_ids
        )

        if needs_review:
            run.await_review()
        else:
            run.complete()
        return PipelineOutcome(
            run_id=run.id, final_status=run.status, result=result, ingestion=ingestion
        )

    # --- stage runner (durable checkpoint + fail-safe boundary) ----------------------------
    async def _run_stage(
        self, run: ExtractionRun, stage: ExtractionStage, operation: Awaitable[_T]
    ) -> _T:
        run.start_stage(stage_execution_id=self._new_stage_execution_id(), stage=stage)
        try:
            outcome = await operation
        except Exception as exc:  # fail-safe orchestration boundary: never leave a partial run
            error = ExtractionError(
                stage=stage, code=type(exc).__name__, message=str(exc) or type(exc).__name__
            )
            run.fail_stage(stage=stage, error=error)
            run.fail(error=error)
            raise PipelineError(run.id, error) from exc
        run.complete_stage(stage=stage)
        return outcome

    # --- per-stage work (pure composition over the ports) ----------------------------------
    async def _extract_objects(
        self, tree: SegmentTree, context: ExtractionContext
    ) -> tuple[ExtractionCandidate, ...]:
        extractors = self._ports.extractors.resolve(context.profile)
        collected: list[ExtractionCandidate] = []
        for segment in tree.segments:
            for extractor in extractors:
                candidate_set = await extractor.extract(segment, context)
                collected.extend(candidate_set.objects)
        return tuple(collected)

    async def _extract_relationships(
        self, candidates: tuple[ExtractionCandidate, ...], context: ExtractionContext
    ) -> tuple[CandidateRelationship, ...]:
        edges: list[CandidateRelationship] = []
        for relationship_extractor in self._ports.relationship_extractors:
            edges.extend(await relationship_extractor.extract(candidates, context))
        mapper = self._ports.framework_mapper
        if mapper is not None:
            for candidate in candidates:
                if candidate.object_type in _MAPPABLE_OBJECT_TYPES:
                    edges.extend(await mapper.map_candidate(candidate, context))
        return tuple(edges)

    async def _score(
        self, candidates: tuple[ExtractionCandidate, ...], classification: ClassificationResult
    ) -> tuple[ExtractionCandidate, ...]:
        scored: list[ExtractionCandidate] = []
        for candidate in candidates:
            signals = ScoringSignals(
                extractor_confidence=candidate.confidence,
                classification_confidence=classification.confidence,
            )
            confidence = await self._ports.scorer.score(candidate, signals=signals)
            scored.append(replace(candidate, confidence=confidence))
        return tuple(scored)

    def _document_plan(self, run: ExtractionRun, tree: SegmentTree, language: str) -> DocumentPlan:
        sections = tuple(
            SectionPlan(
                anchor=segment.anchor,
                position=segment.position,
                page_range=segment.page_range,
                parent_index=segment.parent_index,
            )
            for segment in tree.segments
        )
        return DocumentPlan(
            language=language,
            document_format=run.raw_document.declared_format,
            storage_locator=run.raw_document.storage_locator,
            content_hash=run.raw_document.content_hash,
            sections=sections,
        )


def _empty_result(run: ExtractionRun) -> ExtractionResult:
    """The result placeholder for an idempotent (already-ingested) run."""
    return ExtractionResult(
        run_id=run.id,
        scope=run.scope,
        source_id=run.source_id,
        version_id=run.version_id,
        pipeline_version=run.pipeline_version,
    )
