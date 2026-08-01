"""The orchestrator's own coordination model: stages, status, result, metrics, hooks,
cancellation, and errors. These are pipeline-*run* shapes (how one execution went), not
pipeline contracts (what flows between engines) — the latter live in pipeline-contracts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from answer_validation import ValidatedAnswer
from pipeline_contracts import (
    Answer,
    ContextPackage,
    DecisionPlan,
    LLMRequest,
    RetrievedContext,
    UserRequest,
    dataclass_dict,
)
from pipeline_tracing import Trace


class PipelineStage(str, Enum):
    DECISION = "decision"
    RETRIEVAL = "retrieval"
    CONTEXT = "context"
    PROMPT = "prompt"
    APPROVAL = "approval"
    GENERATION = "generation"
    VALIDATION = "validation"  # optional post-generation answer validation (Phase 13)


class PipelineStatus(str, Enum):
    COMPLETED = "completed"
    AWAITING_APPROVAL = "awaiting_approval"   # the human gate paused the run before generation
    INVALID_PROMPT = "invalid_prompt"         # fail-safe: an invalid LLMRequest is never sent


class PipelineStageError(Exception):
    """Wraps any failure inside a stage so callers always know *where* the pipeline broke.
    The original exception is chained as `__cause__`."""

    def __init__(self, stage: PipelineStage, trace_id: str, message: str) -> None:
        super().__init__(f"[{trace_id}] stage '{stage.value}' failed: {message}")
        self.stage = stage
        self.trace_id = trace_id


class PipelineCancelled(Exception):
    """Raised when a `CancellationToken` is triggered; carries the stage that was about to
    run. Nothing consequential has happened by then — generation is the only external call
    and it is always the last stage."""

    def __init__(self, stage: PipelineStage, trace_id: str) -> None:
        super().__init__(f"[{trace_id}] pipeline cancelled before stage '{stage.value}'")
        self.stage = stage
        self.trace_id = trace_id


class CancellationToken:
    """Cooperative cancellation: the caller keeps the token and may cancel at any moment;
    the orchestrator checks it before every stage."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


@dataclass(frozen=True)
class ApprovalRequest:
    """What a human gate gets to see before the pipeline proceeds to generation: the plan
    that demanded the gate and the exact request that would be sent."""

    trace_id: str
    plan: DecisionPlan
    llm_request: LLMRequest


@dataclass
class PipelineHooks:
    """The extension surface. All hooks are optional; the pipeline runs identically with
    none configured. `on_event` is the future event-bus hook (it receives every lifecycle
    event by name); `approval_gate` is the future human-approval hook — when set, a plan
    with `requires_human_gate` pauses the run unless the gate returns True."""

    on_stage_start: Callable[[PipelineStage, str], None] | None = None
    on_stage_end: Callable[[PipelineStage, str, float], None] | None = None
    on_event: Callable[[str, dict[str, object]], None] | None = None
    approval_gate: Callable[[ApprovalRequest], bool] | None = None


@dataclass
class PipelineMetrics:
    """Per-run observability: where the time went and what the prompt/generation cost."""

    trace_id: str
    timings_ms: dict[str, float] = field(default_factory=dict)
    total_ms: float = 0.0
    estimated_prompt_tokens: int = 0
    usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(
            self,
            extra={
                "timings_ms": {k: round(v, 2) for k, v in self.timings_ms.items()},
                "total_ms": round(self.total_ms, 2),
            },
        )


@dataclass
class PipelineResult:
    """The full, auditable record of one pipeline run: every intermediate artifact is kept
    so an auditor (or a resume after a human gate) can reconstruct exactly what happened."""

    status: PipelineStatus
    trace_id: str
    request: UserRequest
    plan: DecisionPlan
    retrieved: RetrievedContext | None
    context: ContextPackage | None
    llm_request: LLMRequest | None
    answer: Answer | None
    metrics: PipelineMetrics
    warnings: list[str] = field(default_factory=list)
    # Phase 13 additive fields — populated only when the corresponding capability is wired;
    # both default to None so a run without them serializes exactly as before.
    validated: ValidatedAnswer | None = None
    trace: Trace | None = None

    def to_dict(self) -> dict[str, object]:
        # `request` stays out of the record: the query is already inside plan/llm_request
        return dataclass_dict(self, exclude=("request",))
