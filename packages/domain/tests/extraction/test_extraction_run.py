"""Unit tests for the ExtractionRun aggregate lifecycle and stage tracking."""
from __future__ import annotations

import pytest
from grc_domain.extraction import (
    ExtractionError,
    ExtractionRun,
    ExtractionRunStatus,
    ExtractionStage,
    RawDocumentDescriptor,
    StageStatus,
)
from grc_domain.extraction.events import (
    ExtractionRunCompleted,
    ExtractionRunFailed,
    ExtractionRunOpened,
    ExtractionRunResumed,
    ExtractionRunStarted,
    ExtractionRunSuperseded,
    ExtractionStageCompleted,
)
from grc_domain.extraction.exceptions import (
    IllegalExtractionRunTransition,
    IllegalStageTransition,
    StageExecutionNotFound,
)
from grc_domain.knowledge import ContentHash, DocumentFormat, KnowledgeScope, StorageLocator
from grc_domain.shared.identifiers import (
    ExtractionRunId,
    KnowledgeObjectId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
    StageExecutionId,
)

RUN = ExtractionRunId("run-1")
SRC = KnowledgeSourceId("src-1")
VER = KnowledgeSourceVersionId("ver-1")
SCOPE = KnowledgeScope.global_()
RAW = RawDocumentDescriptor(
    storage_locator=StorageLocator("s3://bucket/raw.pdf"),
    content_hash=ContentHash("sha256", "abc"),
    declared_format=DocumentFormat.PDF,
)


def make_run() -> ExtractionRun:
    return ExtractionRun.open(
        id=RUN,
        scope=SCOPE,
        source_id=SRC,
        version_id=VER,
        raw_document=RAW,
        idempotency_key="key-1",
        pipeline_version="1.0.0",
    )


def err(
    stage: ExtractionStage = ExtractionStage.PARSE, *, retryable: bool = True
) -> ExtractionError:
    return ExtractionError(stage=stage, code="failed", message="boom", retryable=retryable)


# --- construction --------------------------------------------------------------------------
def test_open_starts_pending_with_event() -> None:
    run = make_run()
    assert run.status is ExtractionRunStatus.PENDING
    assert run.is_active
    assert any(isinstance(e, ExtractionRunOpened) for e in run.pending_events)


def test_open_validates_required_strings() -> None:
    with pytest.raises(ValueError):
        ExtractionRun.open(
            id=RUN, scope=SCOPE, source_id=SRC, version_id=VER, raw_document=RAW,
            idempotency_key="  ", pipeline_version="1.0.0",
        )
    with pytest.raises(ValueError):
        ExtractionRun.open(
            id=RUN, scope=SCOPE, source_id=SRC, version_id=VER, raw_document=RAW,
            idempotency_key="k", pipeline_version="   ",
        )


# --- happy path ----------------------------------------------------------------------------
def test_full_run_to_completion() -> None:
    run = make_run()
    run.begin()
    assert run.status is ExtractionRunStatus.RUNNING
    assert run.started_at is not None

    run.start_stage(stage_execution_id=StageExecutionId("se-1"), stage=ExtractionStage.PARSE)
    run.complete_stage(stage=ExtractionStage.PARSE, artifact_ref="hash:parsed")
    parse_exec = run.last_stage_execution
    assert parse_exec is not None
    assert parse_exec.status is StageStatus.SUCCEEDED
    assert parse_exec.artifact_ref == "hash:parsed"

    run.start_stage(stage_execution_id=StageExecutionId("se-2"), stage=ExtractionStage.PERSIST)
    run.record_results(
        object_ids=(KnowledgeObjectId("obj-1"),),
        relationship_ids=(),
    )
    run.complete_stage(stage=ExtractionStage.PERSIST)
    run.await_review()
    # mypy narrows run.status to the previous assert's literal and doesn't see that
    # await_review() mutates it via _transition(); this is a real state change at runtime.
    assert run.status == ExtractionRunStatus.AWAITING_REVIEW  # type: ignore[comparison-overlap]

    run.complete()
    assert run.status is ExtractionRunStatus.COMPLETED
    assert run.is_terminal
    assert run.finished_at is not None
    assert run.produced_object_ids == (KnowledgeObjectId("obj-1"),)

    types = {type(e) for e in run.pending_events}
    assert ExtractionRunStarted in types
    assert ExtractionStageCompleted in types
    assert ExtractionRunCompleted in types


# --- stage tracking ------------------------------------------------------------------------
def test_stage_cannot_start_unless_running() -> None:
    run = make_run()  # still PENDING
    with pytest.raises(IllegalStageTransition):
        run.start_stage(stage_execution_id=StageExecutionId("se-1"), stage=ExtractionStage.PARSE)


def test_complete_stage_without_running_execution_raises() -> None:
    run = make_run()
    run.begin()
    with pytest.raises(StageExecutionNotFound):
        run.complete_stage(stage=ExtractionStage.PARSE)


def test_retried_stage_increments_attempt() -> None:
    run = make_run()
    run.begin()
    run.start_stage(stage_execution_id=StageExecutionId("se-1"), stage=ExtractionStage.PARSE)
    run.fail_stage(stage=ExtractionStage.PARSE, error=err())
    # a second attempt at the same stage
    run.start_stage(stage_execution_id=StageExecutionId("se-2"), stage=ExtractionStage.PARSE)
    assert run.last_stage_execution is not None
    assert run.last_stage_execution.attempt == 2


def test_record_results_requires_running() -> None:
    run = make_run()  # PENDING
    with pytest.raises(IllegalStageTransition):
        run.record_results(object_ids=(KnowledgeObjectId("obj-1"),))


# --- failure / resume / cancel / supersede -------------------------------------------------
def test_fail_then_resume() -> None:
    run = make_run()
    run.begin()
    objects = ExtractionStage.EXTRACT_OBJECTS
    run.start_stage(stage_execution_id=StageExecutionId("se-1"), stage=objects)
    run.fail_stage(stage=objects, error=err(objects))
    run.fail(error=err(objects))
    assert run.status is ExtractionRunStatus.FAILED
    assert run.error is not None
    assert any(isinstance(e, ExtractionRunFailed) for e in run.pending_events)

    run.resume()
    # mypy narrows run.status to the previous assert's literal and doesn't see that
    # resume() mutates it via _transition(); this is a real state change at runtime.
    assert run.status == ExtractionRunStatus.RUNNING  # type: ignore[comparison-overlap]
    assert run.error is None
    assert any(isinstance(e, ExtractionRunResumed) for e in run.pending_events)


def test_cancel_from_running() -> None:
    run = make_run()
    run.begin()
    run.cancel()
    assert run.status is ExtractionRunStatus.CANCELLED
    assert run.is_terminal


def test_supersede_completed_run() -> None:
    run = make_run()
    run.begin()
    run.await_review()
    run.complete()
    successor = ExtractionRunId("run-2")
    run.supersede(superseded_by_run_id=successor)
    assert run.status is ExtractionRunStatus.SUPERSEDED
    assert run.superseded_by_run_id == successor
    assert any(isinstance(e, ExtractionRunSuperseded) for e in run.pending_events)


# --- illegal transitions -------------------------------------------------------------------
def test_cannot_complete_from_pending() -> None:
    run = make_run()
    with pytest.raises(IllegalExtractionRunTransition):
        run.complete()


def test_cannot_resume_a_running_run() -> None:
    run = make_run()
    run.begin()
    with pytest.raises(IllegalExtractionRunTransition):
        run.resume()


def test_cancelled_run_is_terminal() -> None:
    run = make_run()
    run.begin()
    run.cancel()
    with pytest.raises(IllegalExtractionRunTransition):
        run.begin()
