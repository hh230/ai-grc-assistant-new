"""End-to-end tests: a raw text document through the real rule-based adapters + the coordinator.

These prove the whole Knowledge Extraction Engine works as an integrated unit — parse → normalize
→ segment → classify → extract → score → persist — with provenance preserved and idempotency
honored, using no LLM and no database.
"""
from __future__ import annotations

import itertools

from grc_domain.extraction import ExtractionRun, ExtractionRunStatus, RawDocumentDescriptor
from grc_domain.extraction.enums import StageStatus
from grc_domain.knowledge import (
    ContentHash,
    DocumentFormat,
    DocumentType,
    KnowledgeObjectType,
    KnowledgeScope,
    StorageLocator,
)
from grc_domain.shared.identifiers import (
    ExtractionRunId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
    StageExecutionId,
)
from grc_extraction import StageExecutionIdFactory
from grc_extraction_adapters import (
    InMemoryKnowledgeIngestion,
    build_pipeline,
    default_profile,
)

POLICY_URI = "mem://policy"
POLICY_TEXT = (
    "Article 5: Security Controls\n"
    "The controller shall implement appropriate technical controls.\n"
    "Article 6: Definitions\n"
    '"Personal Data" means any information relating to an identified natural person.\n'
)

SCOPE = KnowledgeScope.global_()
SRC = KnowledgeSourceId("src-1")
VER = KnowledgeSourceVersionId("ver-1")


def counter_ids() -> StageExecutionIdFactory:
    counter = itertools.count(1)

    def _next() -> StageExecutionId:
        return StageExecutionId(f"se-{next(counter)}")

    return _next


def make_run(run_id: str = "run-e2e", content: str = "policy-hash") -> ExtractionRun:
    return ExtractionRun.open(
        id=ExtractionRunId(run_id),
        scope=SCOPE,
        source_id=SRC,
        version_id=VER,
        raw_document=RawDocumentDescriptor(
            storage_locator=StorageLocator(POLICY_URI),
            content_hash=ContentHash("sha256", content),
            declared_format=DocumentFormat.TXT,
            declared_language="en",
        ),
        idempotency_key="key-1",
        pipeline_version="1.0.0",
    )


async def test_real_adapters_extract_requirement_and_definition() -> None:
    ingestion = InMemoryKnowledgeIngestion()
    pipeline = build_pipeline(
        {POLICY_URI: POLICY_TEXT}, ingestion=ingestion, new_stage_execution_id=counter_ids()
    )
    run = make_run()

    outcome = await pipeline.run(run, profile=default_profile(DocumentType.STANDARD))

    assert run.status is ExtractionRunStatus.COMPLETED
    object_types = {candidate.object_type for candidate in outcome.result.objects}
    assert object_types == {KnowledgeObjectType.REQUIREMENT, KnowledgeObjectType.DEFINITION}
    assert all(candidate.provenance.anchor is not None for candidate in outcome.result.objects)
    assert len(outcome.ingestion.object_ids) == len(outcome.result.objects)
    assert len(ingestion.persisted) == 1
    # one document manifestation with a section per recovered segment
    assert len(outcome.result.documents) == 1
    assert len(outcome.result.documents[0].sections) == 2


async def test_all_stages_succeed_end_to_end() -> None:
    pipeline = build_pipeline({POLICY_URI: POLICY_TEXT}, new_stage_execution_id=counter_ids())
    run = make_run()

    await pipeline.run(run, profile=default_profile(DocumentType.STANDARD))

    assert len(run.stage_executions) == 9
    assert all(execution.status is StageStatus.SUCCEEDED for execution in run.stage_executions)


async def test_reingesting_same_content_is_idempotent() -> None:
    ingestion = InMemoryKnowledgeIngestion()
    pipeline = build_pipeline(
        {POLICY_URI: POLICY_TEXT}, ingestion=ingestion, new_stage_execution_id=counter_ids()
    )

    first = await pipeline.run(make_run("run-1"), profile=default_profile(DocumentType.STANDARD))
    second = await pipeline.run(make_run("run-2"), profile=default_profile(DocumentType.STANDARD))

    assert first.deduplicated is False
    assert second.deduplicated is True
    assert len(ingestion.persisted) == 1  # second run reused the first ingestion
