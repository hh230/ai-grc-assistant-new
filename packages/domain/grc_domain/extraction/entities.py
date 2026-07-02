"""The ExtractionRun aggregate and its StageExecution child entity.

ExtractionRun is the engine's flagship aggregate: a durable, resumable, idempotent record of
turning one raw document into canonical Knowledge Objects. It enforces a fail-safe lifecycle
(no partial publication) and records every stage attempt for audit and resumability. It is
pure domain logic — the pipeline coordinator, ports, and adapters live in outer layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..knowledge import KnowledgeScope
from ..shared.entity import AggregateRoot, Entity, utcnow
from ..shared.identifiers import (
    ExtractionRunId,
    KnowledgeObjectId,
    KnowledgeRelationshipId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
    StageExecutionId,
)
from .enums import ExtractionRunStatus, ExtractionStage, StageStatus
from .events import (
    ExtractionRunAwaitingReview,
    ExtractionRunCancelled,
    ExtractionRunCompleted,
    ExtractionRunFailed,
    ExtractionRunOpened,
    ExtractionRunResumed,
    ExtractionRunStarted,
    ExtractionRunSuperseded,
    ExtractionStageCompleted,
    ExtractionStageFailed,
    ExtractionStageStarted,
)
from .exceptions import (
    IllegalExtractionRunTransition,
    IllegalStageTransition,
    StageExecutionNotFound,
)
from .value_objects import ExtractionError, RawDocumentDescriptor

# Allowed run-status transitions (status -> reachable statuses).
_RUN_TRANSITIONS: dict[ExtractionRunStatus, frozenset[ExtractionRunStatus]] = {
    ExtractionRunStatus.PENDING: frozenset(
        {
            ExtractionRunStatus.RUNNING,
            ExtractionRunStatus.FAILED,
            ExtractionRunStatus.CANCELLED,
            ExtractionRunStatus.SUPERSEDED,
        }
    ),
    ExtractionRunStatus.RUNNING: frozenset(
        {
            ExtractionRunStatus.AWAITING_REVIEW,
            ExtractionRunStatus.COMPLETED,
            ExtractionRunStatus.FAILED,
            ExtractionRunStatus.CANCELLED,
            ExtractionRunStatus.SUPERSEDED,
        }
    ),
    ExtractionRunStatus.AWAITING_REVIEW: frozenset(
        {
            ExtractionRunStatus.COMPLETED,
            ExtractionRunStatus.RUNNING,  # re-extract / apply corrections
            ExtractionRunStatus.FAILED,
            ExtractionRunStatus.CANCELLED,
            ExtractionRunStatus.SUPERSEDED,
        }
    ),
    ExtractionRunStatus.FAILED: frozenset(
        {
            ExtractionRunStatus.RUNNING,  # resume
            ExtractionRunStatus.CANCELLED,
            ExtractionRunStatus.SUPERSEDED,
        }
    ),
    ExtractionRunStatus.COMPLETED: frozenset({ExtractionRunStatus.SUPERSEDED}),
    ExtractionRunStatus.CANCELLED: frozenset(),
    ExtractionRunStatus.SUPERSEDED: frozenset(),
}

_ACTIVE_STATUSES: frozenset[ExtractionRunStatus] = frozenset(
    {
        ExtractionRunStatus.PENDING,
        ExtractionRunStatus.RUNNING,
        ExtractionRunStatus.AWAITING_REVIEW,
        ExtractionRunStatus.FAILED,
    }
)


@dataclass(eq=False)
class StageExecution(Entity):
    """One execution (attempt) of a single pipeline stage — a durable checkpoint."""

    id: StageExecutionId
    stage: ExtractionStage
    status: StageStatus = StageStatus.RUNNING
    attempt: int = 1
    processor_name: str | None = None
    processor_version: str | None = None
    artifact_ref: str | None = None
    error: ExtractionError | None = None
    started_at: datetime = field(default_factory=utcnow)
    finished_at: datetime | None = None

    @property
    def is_running(self) -> bool:
        return self.status is StageStatus.RUNNING


@dataclass(kw_only=True, eq=False)
class ExtractionRun(AggregateRoot):
    """A durable, resumable extraction run targeting one draft KnowledgeSourceVersion."""

    id: ExtractionRunId
    scope: KnowledgeScope
    source_id: KnowledgeSourceId
    version_id: KnowledgeSourceVersionId
    raw_document: RawDocumentDescriptor
    idempotency_key: str
    pipeline_version: str
    status: ExtractionRunStatus = ExtractionRunStatus.PENDING
    stage_executions: list[StageExecution] = field(default_factory=list)
    produced_object_ids: tuple[KnowledgeObjectId, ...] = field(default_factory=tuple)
    produced_relationship_ids: tuple[KnowledgeRelationshipId, ...] = field(
        default_factory=tuple
    )
    error: ExtractionError | None = None
    superseded_by_run_id: ExtractionRunId | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    # ---- construction ----
    @classmethod
    def open(
        cls,
        *,
        id: ExtractionRunId,
        scope: KnowledgeScope,
        source_id: KnowledgeSourceId,
        version_id: KnowledgeSourceVersionId,
        raw_document: RawDocumentDescriptor,
        idempotency_key: str,
        pipeline_version: str,
    ) -> ExtractionRun:
        if not idempotency_key.strip():
            raise ValueError("ExtractionRun idempotency_key must not be empty")
        if not pipeline_version.strip():
            raise ValueError("ExtractionRun pipeline_version must not be empty")
        run = cls(
            id=id,
            scope=scope,
            source_id=source_id,
            version_id=version_id,
            raw_document=raw_document,
            idempotency_key=idempotency_key.strip(),
            pipeline_version=pipeline_version.strip(),
        )
        run._record_event(
            ExtractionRunOpened(run_id=id, scope=scope, version_id=version_id)
        )
        return run

    # ---- helpers ----
    def _transition(self, target: ExtractionRunStatus) -> None:
        if target not in _RUN_TRANSITIONS[self.status]:
            raise IllegalExtractionRunTransition(
                f"Cannot move extraction run from {self.status.value} to {target.value}"
            )
        self.status = target

    def _running_stage(self, stage: ExtractionStage) -> StageExecution:
        for execution in reversed(self.stage_executions):
            if execution.stage is stage and execution.is_running:
                return execution
        raise StageExecutionNotFound(
            f"No running execution for stage {stage.value} on run {self.id}"
        )

    def _attempts_for(self, stage: ExtractionStage) -> int:
        return sum(1 for execution in self.stage_executions if execution.stage is stage)

    # ---- run lifecycle ----
    def begin(self) -> None:
        self._transition(ExtractionRunStatus.RUNNING)
        if self.started_at is None:
            self.started_at = utcnow()
        self._record_event(ExtractionRunStarted(run_id=self.id))

    def await_review(self) -> None:
        self._transition(ExtractionRunStatus.AWAITING_REVIEW)
        self._record_event(ExtractionRunAwaitingReview(run_id=self.id))

    def complete(self) -> None:
        self._transition(ExtractionRunStatus.COMPLETED)
        self.finished_at = utcnow()
        self._record_event(ExtractionRunCompleted(run_id=self.id))

    def fail(self, *, error: ExtractionError) -> None:
        self._transition(ExtractionRunStatus.FAILED)
        self.error = error
        self.finished_at = utcnow()
        self._record_event(ExtractionRunFailed(run_id=self.id, reason=error.message))

    def resume(self) -> None:
        self._transition(ExtractionRunStatus.RUNNING)
        self.error = None
        self.finished_at = None
        self._record_event(ExtractionRunResumed(run_id=self.id))

    def cancel(self) -> None:
        self._transition(ExtractionRunStatus.CANCELLED)
        self.finished_at = utcnow()
        self._record_event(ExtractionRunCancelled(run_id=self.id))

    def supersede(self, *, superseded_by_run_id: ExtractionRunId) -> None:
        self._transition(ExtractionRunStatus.SUPERSEDED)
        self.superseded_by_run_id = superseded_by_run_id
        self._record_event(
            ExtractionRunSuperseded(
                run_id=self.id, superseded_by_run_id=superseded_by_run_id
            )
        )

    # ---- stage tracking (checkpoints) ----
    def start_stage(
        self,
        *,
        stage_execution_id: StageExecutionId,
        stage: ExtractionStage,
        processor_name: str | None = None,
        processor_version: str | None = None,
    ) -> None:
        if self.status is not ExtractionRunStatus.RUNNING:
            raise IllegalStageTransition(
                "Stages run only while the extraction run is RUNNING"
            )
        execution = StageExecution(
            id=stage_execution_id,
            stage=stage,
            status=StageStatus.RUNNING,
            attempt=self._attempts_for(stage) + 1,
            processor_name=processor_name,
            processor_version=processor_version,
        )
        self.stage_executions.append(execution)
        self._touch()
        self._record_event(ExtractionStageStarted(run_id=self.id, stage=stage))

    def complete_stage(
        self, *, stage: ExtractionStage, artifact_ref: str | None = None
    ) -> None:
        execution = self._running_stage(stage)
        execution.status = StageStatus.SUCCEEDED
        execution.artifact_ref = artifact_ref
        execution.finished_at = utcnow()
        execution._touch()
        self._touch()
        self._record_event(ExtractionStageCompleted(run_id=self.id, stage=stage))

    def fail_stage(self, *, stage: ExtractionStage, error: ExtractionError) -> None:
        execution = self._running_stage(stage)
        execution.status = StageStatus.FAILED
        execution.error = error
        execution.finished_at = utcnow()
        execution._touch()
        self._touch()
        self._record_event(
            ExtractionStageFailed(run_id=self.id, stage=stage, reason=error.message)
        )

    def record_results(
        self,
        *,
        object_ids: tuple[KnowledgeObjectId, ...] = (),
        relationship_ids: tuple[KnowledgeRelationshipId, ...] = (),
    ) -> None:
        """Record the canonical objects/relationships produced (set during PERSIST)."""
        if self.status is not ExtractionRunStatus.RUNNING:
            raise IllegalStageTransition(
                "Results can only be recorded while the run is RUNNING"
            )
        self.produced_object_ids = tuple(object_ids)
        self.produced_relationship_ids = tuple(relationship_ids)
        self._touch()

    # ---- queries ----
    @property
    def is_active(self) -> bool:
        return self.status in _ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ExtractionRunStatus.COMPLETED,
            ExtractionRunStatus.CANCELLED,
            ExtractionRunStatus.SUPERSEDED,
        )

    @property
    def last_stage_execution(self) -> StageExecution | None:
        return self.stage_executions[-1] if self.stage_executions else None
