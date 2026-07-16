"""Rasheed V2 Pipeline Tool (Phase 15, step 3) — the first Tool and the first vertical slice.

`PipelineTool` wraps the existing AI Orchestrator (ADR 0038) as a registered `Tool`, so the
platform's one-shot grounded pipeline becomes a capability a Mission can invoke. `RegistryExecutor`
implements the Mission Engine's `ExecutionPort` by resolving a step to a Tool via the Tool
Registry and invoking it. Together they close the slice:

    Mission → ExecutionPort → RegistryExecutor → Registry → PipelineTool → AI Orchestrator → Answer

This is a composition/adapter package: it wires existing pieces together, adds no new domain, and
imports no LLM SDK.
"""

from pipeline_tool.contract import (
    PAYLOAD_INSTRUCTION,
    PAYLOAD_TRACE_ID,
    ToolStepResult,
)
from pipeline_tool.executor import RegistryExecutor
from pipeline_tool.runner import PipelineRunner
from pipeline_tool.tool import RUN_PIPELINE_TOOL, PipelineTool

__all__ = [
    # the tool + its runner port
    "PipelineTool",
    "PipelineRunner",
    "RUN_PIPELINE_TOOL",
    # the executor bridge
    "RegistryExecutor",
    # the shared mission-step tool contract (what any mission-invokable tool speaks)
    "ToolStepResult",
    "PAYLOAD_INSTRUCTION",
    "PAYLOAD_TRACE_ID",
]
