"""The AI Orchestrator — the composition root and single entry point of the AI pipeline.

    UserRequest
      → DecisionEngine        (what to do — classification lives there, not here)
      → RetrievalEngine       (what we know — only when the plan requires retrieval)
      → ContextBuilder        (structure the evidence, citations preserved)
      → PromptOrchestrator    (the provider-agnostic LLMRequest)
      → GenerationEngine      (retry/metrics/error boundary, via the GenerationProvider port)
    → Answer (inside a fully auditable PipelineResult)

This class owns *only* coordination: sequencing, wiring/DI, execution flow, metrics,
tracing, error propagation, cancellation, and the future event / human-approval hooks.
It performs no retrieval, builds no prompts, classifies nothing, and contains no business
rules — every capability belongs to the engine that already owns it. The orchestrator is
stateless: all per-run state lives in the `PipelineResult` it returns.

Fail-safe policies (CLAUDE.md §16):
  • an `LLMRequest` that failed validation is never sent to a provider;
  • a plan that requires a human gate pauses before generation when a gate is configured;
  • retrieval demanded but not wired degrades to the prompt layer's explicit
    insufficient-evidence handling, with a warning — never a silent guess.
"""

from __future__ import annotations

import contextlib
import time
import uuid
from collections.abc import Callable
from typing import TypeVar

from answer_validation import AnswerValidator, ValidatedAnswer
from context_builder import ContextBuilder
from decision_engine import DecisionEngine
from event_bus import (
    AnswerValidated,
    DomainEvent,
    EventBus,
    GenerationCompleted,
    PipelineCompleted,
    PromptBuilt,
    RetrievalCompleted,
)
from pipeline_contracts import (
    Answer,
    ContextPackage,
    DecisionPlan,
    Filter,
    GenerationProvider,
    Intent,
    LLMRequest,
    RetrievalQuery,
    RetrievalScope,
    RetrievedContext,
    UserRequest,
)
from pipeline_tracing import Trace, Tracer
from prompt_orchestrator import PromptOrchestrator
from retrieval_engine import RetrievalEngine

from ai_orchestrator.models import (
    ApprovalRequest,
    CancellationToken,
    PipelineCancelled,
    PipelineHooks,
    PipelineMetrics,
    PipelineResult,
    PipelineStage,
    PipelineStageError,
    PipelineStatus,
)

T = TypeVar("T")


class AIOrchestrator:
    """Constructor-injected wiring — the one place the concrete engines meet. Generation
    is injected strictly as the shared `GenerationProvider` port; in production that is a
    `GenerationEngine` (which satisfies the port) wrapping a provider adapter, so retry,
    metrics, and error translation live there — never here. The orchestrator never imports
    a provider SDK. `retrieval_engine` is optional so a deployment without a knowledge
    corpus still answers (ungrounded, flagged)."""

    def __init__(
        self,
        *,
        decision_engine: DecisionEngine,
        context_builder: ContextBuilder,
        prompt_orchestrator: PromptOrchestrator,
        generation_provider: GenerationProvider,
        retrieval_engine: RetrievalEngine | None = None,
        hooks: PipelineHooks | None = None,
        answer_validator: AnswerValidator | None = None,
        event_bus: EventBus | None = None,
        enable_tracing: bool = False,
    ) -> None:
        self._decision = decision_engine
        self._retrieval = retrieval_engine
        self._context = context_builder
        self._prompt = prompt_orchestrator
        self._generation = generation_provider
        self._hooks = hooks or PipelineHooks()
        # Phase 13 hardening collaborators — all optional. With every one left unset the run
        # executes exactly as before: no validation stage, no domain events, no trace object.
        self._validator = answer_validator
        self._bus = event_bus
        self._tracing = enable_tracing

    # ── the single entry point ────────────────────────────────────────────────
    def run(
        self,
        request: UserRequest,
        *,
        mission_id: str,
        cancellation: CancellationToken | None = None,
        trace_id: str | None = None,
    ) -> PipelineResult:
        # `mission_id` is required — every run happens inside a mission (ADR 0042 §11/§12.2), so
        # every event and audit record this run emits is reachable through exactly one mission.
        # The tenant, likewise, is never optional (it rides on the request, ADR 0040 §4).
        started = time.perf_counter()
        trace = trace_id or uuid.uuid4().hex
        token = cancellation or CancellationToken()
        # `request` is a fully-formed `UserRequest` carrying its tenant (ADR 0040 §4) — there is
        # no dict path, because a tenant may not be parsed from an untrusted body (§3).
        user_request = request
        # The tenant scopes retrieval and stamps the audit; `mission_id` is supplied by the
        # caller (every run happens inside a mission, ADR 0042 §11/§12.2). Both stamp every
        # event and the audit record this run emits.
        tenant_id = request.tenant.tenant_id
        metrics = PipelineMetrics(trace_id=trace)
        warnings: list[str] = []
        tracer = Tracer(trace_id=trace) if self._tracing else None
        trace_obj = tracer.trace if tracer else None
        self._emit("pipeline.started", {"trace_id": trace})

        # 1. decide
        plan: DecisionPlan = self._stage(
            PipelineStage.DECISION, trace, token, metrics,
            lambda: self._decision.decide(user_request), tracer,
        )

        # 2. retrieve (only when the plan says so)
        retrieved: RetrievedContext | None = None
        if plan.requires_retrieval:
            if self._retrieval is None:
                warnings.append(
                    "plan requires retrieval but no retrieval engine is wired; "
                    "proceeding ungrounded with insufficient-evidence handling"
                )
            else:
                retrieved = self._stage(
                    PipelineStage.RETRIEVAL, trace, token, metrics,
                    lambda: self._retrieval.retrieve(self._query_from(plan, user_request)), tracer,
                )
                self._publish(
                    _retrieval_event(trace, tenant_id, mission_id, retrieved), warnings
                )

        # 3. build context (only when something was retrieved)
        package: ContextPackage | None = None
        if retrieved is not None:
            package = self._stage(
                PipelineStage.CONTEXT, trace, token, metrics,
                lambda: self._context.build(retrieved, workflow=plan.intent), tracer,
            )

        # 4. assemble the provider-agnostic request
        llm_request: LLMRequest = self._stage(
            PipelineStage.PROMPT, trace, token, metrics,
            lambda: self._prompt.orchestrate(plan, package, user_request), tracer,
        )
        metrics.estimated_prompt_tokens = llm_request.metrics.estimated_tokens
        self._publish(_prompt_event(trace, tenant_id, mission_id, llm_request, plan), warnings)

        # fail-safe: never send a request that failed prompt validation
        if not llm_request.valid:
            warnings.extend(llm_request.warnings)
            return self._finish(
                PipelineStatus.INVALID_PROMPT, trace, started, user_request, plan,
                retrieved, package, llm_request, None, metrics, warnings,
                tenant_id=tenant_id, mission_id=mission_id, trace_record=trace_obj,
            )

        # 5. human gate (future hook — active only when a gate is configured)
        if plan.requires_human_gate:
            if self._hooks.approval_gate is None:
                warnings.append(
                    "plan requires a human gate but no approval hook is configured; "
                    "generation proceeds — the answer is a proposal, not an applied action"
                )
            else:
                approved = self._stage(
                    PipelineStage.APPROVAL, trace, token, metrics,
                    lambda: bool(
                        self._hooks.approval_gate(ApprovalRequest(trace, plan, llm_request))
                    ), tracer,
                )
                if not approved:
                    return self._finish(
                        PipelineStatus.AWAITING_APPROVAL, trace, started, user_request, plan,
                        retrieved, package, llm_request, None, metrics, warnings,
                        tenant_id=tenant_id, mission_id=mission_id, trace_record=trace_obj,
                    )

        # 6. generate — the only external call, always last
        answer: Answer = self._stage(
            PipelineStage.GENERATION, trace, token, metrics,
            lambda: self._generation.generate(llm_request), tracer,
        )
        metrics.usage = dict(answer.usage)
        self._publish(_generation_event(trace, tenant_id, mission_id, answer), warnings)

        # 7. validate the generated answer (only when a validator is wired). Never mutates
        #    the answer and never fails the run — a poor answer is reported, not suppressed.
        validated: ValidatedAnswer | None = None
        if self._validator is not None:
            validated = self._stage(
                PipelineStage.VALIDATION, trace, token, metrics,
                lambda: self._validator.validate(
                    answer, context=package, contract=llm_request.response_contract
                ), tracer,
            )
            self._publish(_validation_event(trace, tenant_id, mission_id, validated), warnings)
            warnings.extend(w.message for w in validated.warnings)
            warnings.extend(f"validation error: {e.message}" for e in validated.errors)

        return self._finish(
            PipelineStatus.COMPLETED, trace, started, user_request, plan,
            retrieved, package, llm_request, answer, metrics, warnings,
            tenant_id=tenant_id, mission_id=mission_id, validated=validated, trace_record=trace_obj,
        )

    # ── coordination helpers ──────────────────────────────────────────────────
    @staticmethod
    def _query_from(plan: DecisionPlan, request: UserRequest) -> RetrievalQuery:
        """Pure wiring: hand the Decision Engine's routing hints (target profiles,
        language, chunk budget) to the Retrieval Engine's own query contract.
        `plan.context_budget` is a chunk-count budget per the decision-engine workflow
        catalog, so it maps to retrieval depth; token budgeting belongs to the Context
        Builder. Single-pass for now; `plan.retrieval_passes` is a future multi-pass hook."""
        return RetrievalQuery(
            text=request.query,
            # Retrieval is bound to the request's tenant scope (ADR 0040 §4): GLOBAL ∪
            # ORGANIZATION(tenant). The scope is applied inside the providers.
            filter=Filter(
                document_profiles=tuple(plan.target_profiles),
                scope=RetrievalScope.from_context(request.tenant),
            ),
            top_k=max(1, plan.context_budget),
            language=plan.language,
        )

    def _stage(
        self,
        stage: PipelineStage,
        trace: str,
        token: CancellationToken,
        metrics: PipelineMetrics,
        run: Callable[[], T],
        tracer: Tracer | None = None,
    ) -> T:
        if token.cancelled:
            self._emit("pipeline.cancelled", {"trace_id": trace, "stage": stage.value})
            raise PipelineCancelled(stage, trace)
        if self._hooks.on_stage_start:
            self._hooks.on_stage_start(stage, trace)
        self._emit(f"stage.{stage.value}.started", {"trace_id": trace})
        started = time.perf_counter()
        # The tracer span times the stage independently and records failures too; the
        # existing metrics.timings_ms bookkeeping below is left exactly as it was.
        span = tracer.stage(stage.value) if tracer else contextlib.nullcontext()
        try:
            with span:
                result = run()
        except (PipelineCancelled, PipelineStageError):
            raise
        except Exception as exc:
            self._emit(f"stage.{stage.value}.failed", {"trace_id": trace, "error": str(exc)})
            raise PipelineStageError(stage, trace, str(exc)) from exc
        elapsed = (time.perf_counter() - started) * 1000
        metrics.timings_ms[stage.value] = elapsed
        if self._hooks.on_stage_end:
            self._hooks.on_stage_end(stage, trace, elapsed)
        self._emit(f"stage.{stage.value}.completed", {"trace_id": trace, "ms": round(elapsed, 2)})
        return result

    def _publish(self, event: DomainEvent, warnings: list[str]) -> None:
        """Publish a domain event fail-safe: a broken subscriber degrades to a warning and
        never breaks the run (events are observability, not the answer path)."""
        if self._bus is None:
            return
        try:
            self._bus.publish(event)
        except Exception as exc:  # noqa: BLE001 - observability must never fail the pipeline
            warnings.append(f"event publication failed ({event.name}): {exc}")

    def _finish(
        self,
        status: PipelineStatus,
        trace: str,
        started: float,
        request: UserRequest,
        plan: DecisionPlan,
        retrieved: RetrievedContext | None,
        package: ContextPackage | None,
        llm_request: LLMRequest | None,
        answer: Answer | None,
        metrics: PipelineMetrics,
        warnings: list[str],
        *,
        tenant_id: str,
        mission_id: str,
        validated: ValidatedAnswer | None = None,
        trace_record: Trace | None = None,
    ) -> PipelineResult:
        metrics.total_ms = (time.perf_counter() - started) * 1000
        self._emit("pipeline.finished", {"trace_id": trace, "status": status.value})
        # The terminal domain event, published on every path a run can end on — it is what
        # closes the audit trail, so a run that never validated (or never generated) still
        # produces a complete, finalized record.
        self._publish(
            _completion_event(trace, tenant_id, mission_id, status, warnings, metrics), warnings
        )
        return PipelineResult(
            status=status,
            trace_id=trace,
            request=request,
            plan=plan,
            retrieved=retrieved,
            context=package,
            llm_request=llm_request,
            answer=answer,
            metrics=metrics,
            warnings=warnings,
            validated=validated,
            trace=trace_record,
        )

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        if self._hooks.on_event:
            self._hooks.on_event(name, payload)


# ── domain-event builders (pure mapping: pipeline artifacts → summary events) ─────
def _retrieval_event(
    trace: str, tenant_id: str, mission_id: str, retrieved: RetrievedContext
) -> RetrievalCompleted:
    return RetrievalCompleted(
        trace_id=trace,
        tenant_id=tenant_id,
        mission_id=mission_id,
        query=retrieved.query,
        candidates=retrieved.total_candidates,
        results=len(retrieved.results),
        overall_confidence=retrieved.overall_confidence,
        warnings=len(retrieved.warnings),
        source_ids=tuple(chunk.chunk_id for chunk in retrieved.results),
    )


def _prompt_event(
    trace: str, tenant_id: str, mission_id: str, request: LLMRequest, plan: DecisionPlan
) -> PromptBuilt:
    intent = plan.intent
    return PromptBuilt(
        trace_id=trace,
        tenant_id=tenant_id,
        mission_id=mission_id,
        workflow=request.workflow,
        family=request.family.value,
        language=request.language.value,
        estimated_tokens=request.metrics.estimated_tokens,
        segment_count=len(request.segments),
        valid=request.valid,
        intent=intent.value if isinstance(intent, Intent) else str(intent),
        prompt_versions=dict(request.metrics.prompt_versions),
    )


def _generation_event(
    trace: str, tenant_id: str, mission_id: str, answer: Answer
) -> GenerationCompleted:
    return GenerationCompleted(
        trace_id=trace,
        tenant_id=tenant_id,
        mission_id=mission_id,
        provider=answer.provider,
        model=answer.model,
        finish_reason=answer.finish_reason,
        total_tokens=int(answer.usage.get("total_tokens", 0)),
        usage=dict(answer.usage),
        # No cost model exists in the platform yet, so nothing can price a run — the field
        # stays absent rather than carrying a fabricated number.
        estimated_cost=None,
    )


def _completion_event(
    trace: str, tenant_id: str, mission_id: str, status: PipelineStatus,
    warnings: list[str], metrics: PipelineMetrics,
) -> PipelineCompleted:
    return PipelineCompleted(
        trace_id=trace,
        tenant_id=tenant_id,
        mission_id=mission_id,
        status=status.value,
        warnings=len(warnings),
        duration_ms=metrics.total_ms,
    )


def _validation_event(
    trace: str, tenant_id: str, mission_id: str, validated: ValidatedAnswer
) -> AnswerValidated:
    return AnswerValidated(
        trace_id=trace,
        tenant_id=tenant_id,
        mission_id=mission_id,
        status=validated.status.value,
        valid=validated.is_valid,
        error_count=len(validated.errors),
        warning_count=len(validated.warnings),
        confidence_adjustment=validated.confidence_adjustment,
    )
