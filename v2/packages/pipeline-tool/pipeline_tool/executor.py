"""The bridge that closes the vertical slice: `RegistryExecutor` implements the Mission
Engine's `ExecutionPort` (ADR 0042 §12.3) by **resolving a step to a Tool via the Tool
Registry and invoking it** — exactly the seam ADR 0042 §5 describes ("the executor resolves
the step to Tools via the Tool Registry and invokes them"). The Mission Engine dispatches a
`StepRequest`; this executor resolves the tool, invokes it with the step's tenant, and maps the
tool's result dict back to a `StepResult`.

A step may name the tool it runs (`StepRequest.tool`, ADR 0048): the executor resolves that
tool when set, and falls back to its constructor default (`tool_name`) when it is empty — so a
single-tool mission is unchanged and a multi-tool mission routes each step to its own tool, with
no change to the Mission Engine or the Tool Registry.
"""

from __future__ import annotations

from mission_engine import StepRequest, StepResult
from tool_registry import ToolRegistry

from pipeline_tool.contract import (
    PAYLOAD_INSTRUCTION,
    PAYLOAD_MISSION_ID,
    PAYLOAD_PRIOR_CONTEXT,
    PAYLOAD_TRACE_ID,
    ToolStepResult,
)
from pipeline_tool.tool import RUN_PIPELINE_TOOL


class RegistryExecutor:
    """A Mission Engine `ExecutionPort` (satisfied structurally, as the mission-engine adapters
    are) backed by the Tool Registry. Depends only on the two contracts (mission-engine's
    `StepRequest`/`StepResult`, tool-registry's `ToolRegistry`) plus the shared tool-step
    contract; it holds no orchestrator, no pipeline, and no LLM knowledge — that all lives
    behind the resolved tool.

    It maps *any* tool that speaks the `ToolStepResult` contract to a `StepResult`, so a new
    tool (SQL, Risk, Workflow, …) is added by registering it and pointing `tool_name` at it —
    never by editing this class."""

    def __init__(self, registry: ToolRegistry, *, tool_name: str = RUN_PIPELINE_TOOL) -> None:
        self._registry = registry
        self._tool_name = tool_name

    def execute(self, request: StepRequest) -> StepResult:
        # ADR 0048: honour a per-step tool when the plan names one; otherwise fall back to the
        # constructor default. A typo yields ToolNotFound here — fail-safe, surfaced by the
        # mission — never a silent wrong-tool run.
        tool = self._registry.get(request.tool or self._tool_name)
        payload: dict[str, object] = {
            PAYLOAD_INSTRUCTION: request.instruction,
            # nest the step's execution under the mission's trace tree (ADR 0042 §4)
            PAYLOAD_TRACE_ID: request.mission_id,
            # stamp the pipeline's events/audit with the owning mission (ADR 0042 §12.2)
            PAYLOAD_MISSION_ID: request.mission_id,
            # the prior steps' rendered output, so a synthesis tool runs from it (ADR 0051)
            PAYLOAD_PRIOR_CONTEXT: _render_prior_context(request),
        }
        result = ToolStepResult.from_payload(tool.invoke(payload, request.tenant))
        return StepResult(
            step_id=request.step_id,
            ok=result.ok,
            output=result.output,
            source_ids=result.source_ids,
            confidence=result.confidence,
            warnings=result.warnings,
        )


def _render_prior_context(request: StepRequest) -> str:
    """Render the mission's completed step results (ADR 0051) into a readable context block a
    synthesis tool can consume. Empty when there are no prior steps (first step / single-step
    mission), so the payload key is present but inert. Only each step's `output` is included — the
    human-facing result — labelled by ordinal; grounding ids stay on the individual results."""
    steps = [r for r in request.prior_results if r.output.strip()]
    if not steps:
        return ""
    blocks = [f"[Step {i}]\n{r.output.strip()}" for i, r in enumerate(steps, start=1)]
    return "\n\n".join(blocks)
