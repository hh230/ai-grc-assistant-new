"""``DevToolExecutor`` — a new realization of the frozen ``ExecutionPort`` (ADR 0042 §12.3) for the
dev team, resolving each step to a **Dev Tool** via the frozen Tool Registry and invoking it.

This mirrors ``pipeline_tool.RegistryExecutor`` (which resolves a step to the AI pipeline tool) but
stays deliberately **LLM-free**: it depends only on the Mission Engine's ``ExecutionPort`` contract,
the Tool Registry, and the canonical ``ToolStepResult`` — never the ``ai-orchestrator``/generation
stack (the reason that contract lives in ``tool-registry``, ADR 0049). Adding this adapter is the
ports-and-adapters extension seam (``ExecutionPort`` already has ``EchoExecutor`` and
``RegistryExecutor`` as realizations); it changes no frozen component.

Per-step tool selection follows ADR 0048: the executor resolves ``request.tool`` when a plan names
one, else its constructor default. A missing tool raises ``ToolNotFound`` here — fail-safe, surfaced
by the mission as a failed step — never a silent wrong-tool run.
"""

from __future__ import annotations

from mission_engine.ports import StepRequest, StepResult
from tool_registry import ToolRegistry
from tool_registry.result import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT, ToolStepResult


class DevToolExecutor:
    """A Mission Engine ``ExecutionPort`` backed by the Tool Registry of Dev Tools. Satisfied
    structurally (as the frozen adapters are). Maps any tool speaking the ``ToolStepResult``
    contract to a ``StepResult``, so a new dev tool is added by registering it and naming it on a
    ``PlanStep`` — never by editing this class."""

    def __init__(self, registry: ToolRegistry, *, default_tool: str) -> None:
        self._registry = registry
        self._default_tool = default_tool

    def execute(self, request: StepRequest) -> StepResult:
        tool = self._registry.get(request.tool or self._default_tool)
        payload: dict[str, object] = {
            PAYLOAD_INSTRUCTION: request.instruction,
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
    """Render prior steps' output into a readable block a later step can consume (ADR 0051). Empty
    for a first/single step, so the payload key is present but inert."""
    steps = [r for r in request.prior_results if r.output.strip()]
    if not steps:
        return ""
    return "\n\n".join(f"[Step {i}]\n{r.output.strip()}" for i, r in enumerate(steps, start=1))
