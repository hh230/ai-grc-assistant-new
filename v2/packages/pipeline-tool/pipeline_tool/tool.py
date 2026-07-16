"""The Pipeline Tool — the first Tool in the system (ADR 0042, Phase 15 step 3).

Its single job is to run the existing AI Orchestrator as a registered `Tool`, so the platform's
one-shot grounded pipeline becomes a capability a Mission can invoke. It reasons about nothing
and builds nothing: it maps a tool payload to a `UserRequest`, runs the pipeline, and maps the
`PipelineResult` back to a plain result dict (the generic Tool boundary, CLAUDE.md §9). All the
intelligence stays in the Orchestrator and the engines beneath it (ADR 0038).

`required_roles` is left empty and `side_effect` is `READ_ONLY`: answering a grounded question
changes no state. When the Pipeline Tool is asked to do consequential work in a later phase, a
consequential variant declares it and the Mission Engine gates it — the tool never self-gates.
"""

from __future__ import annotations

from ai_orchestrator import PipelineResult, PipelineStatus
from pipeline_contracts import TenantContext, UserRequest
from tool_registry import SideEffectProfile, ToolSpec

from pipeline_tool.contract import (
    PAYLOAD_INSTRUCTION,
    PAYLOAD_MISSION_ID,
    PAYLOAD_TRACE_ID,
    ToolStepResult,
)
from pipeline_tool.runner import PipelineRunner

RUN_PIPELINE_TOOL = "run_pipeline"


class PipelineTool:
    """A `Tool` (satisfies the tool-registry `Tool` protocol) that runs one grounded pipeline
    pass via an injected `PipelineRunner` (the AI Orchestrator in production)."""

    def __init__(self, runner: PipelineRunner, *, version: int = 1) -> None:
        self._runner = runner
        self._spec = ToolSpec(
            name=RUN_PIPELINE_TOOL,
            version=version,
            description="Run one grounded, validated AI pipeline pass and return the answer.",
            side_effect=SideEffectProfile.READ_ONLY,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(
        self, payload: dict[str, object], tenant: TenantContext
    ) -> dict[str, object]:
        # The tenant enters the pipeline here, on the UserRequest (ADR 0040 §4) — carried from
        # the mission step, never parsed from the payload (§3). `mission_id` stamps the run's
        # events/audit (ADR 0042 §12.2).
        query = str(payload.get(PAYLOAD_INSTRUCTION, ""))
        trace = payload.get(PAYLOAD_TRACE_ID)
        mission_id = payload.get(PAYLOAD_MISSION_ID)
        request = UserRequest(
            query=query,
            tenant=tenant,
            has_document=bool(payload.get("has_document", False)),
        )
        result = self._runner.run(
            request,
            mission_id=mission_id if isinstance(mission_id, str) else "",
            trace_id=trace if isinstance(trace, str) else None,
        )
        return self._to_result(result).as_payload()

    @staticmethod
    def _to_result(result: PipelineResult) -> ToolStepResult:
        """Map the rich `PipelineResult` down to the shared mission-step contract: the answer
        text, its grounding (source ids + confidence from retrieval), and any warnings."""
        answer_text = result.answer.text if result.answer is not None else ""
        retrieved = result.retrieved
        source_ids = tuple(chunk.chunk_id for chunk in retrieved.results) if retrieved else ()
        confidence = retrieved.overall_confidence if retrieved is not None else None
        return ToolStepResult(
            ok=result.status is PipelineStatus.COMPLETED,
            output=answer_text,
            source_ids=source_ids,
            confidence=confidence,
            warnings=tuple(result.warnings),
        )
