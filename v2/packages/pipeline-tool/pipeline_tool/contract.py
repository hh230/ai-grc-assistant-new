"""The envelope a Tool invoked as a **mission step** speaks: the payload keys the mission executor
sends, plus the shared result contract it maps back to a `StepResult`.

`ToolStepResult` — the structured result **any** mission-invokable tool returns — now lives in
`tool-registry` (ADR 0049), the pure package every tool depends on, so a leaf tool (Framework
Library, document parser, …) can speak the contract **without depending on this LLM-facing
package**. It is re-exported here so every existing importer
(`from pipeline_tool.contract import ToolStepResult`, `from pipeline_tool import ToolStepResult`)
is unchanged.

The **payload keys** stay here on purpose: they describe how the *mission* executor invokes a tool
(the instruction, the trace/mission ids for audit stamping, ADR 0042 §12.2) — mission knowledge that
does not belong in the pure registry. `RegistryExecutor` writes them; each tool reads the ones it
needs (a control-lookup tool reads only `instruction`).
"""

from __future__ import annotations

from tool_registry import PAYLOAD_INSTRUCTION, PAYLOAD_PRIOR_CONTEXT, ToolStepResult

# The *generic* tool-step input keys (`PAYLOAD_INSTRUCTION`, `PAYLOAD_PRIOR_CONTEXT`) are
# re-exported from `tool-registry` (ADR 0049/0051) so leaf tools read them without this package.
# The *mission-specific* envelope keys stay here — mission knowledge (audit stamping, ADR 0042).
PAYLOAD_TRACE_ID = "trace_id"
# The mission this step runs within (ADR 0042 §12.2). The executor puts the mission id here so
# the tool can stamp the pipeline's events/audit with it — the tool never imports mission-engine.
PAYLOAD_MISSION_ID = "mission_id"

__all__ = [
    "ToolStepResult",
    "PAYLOAD_INSTRUCTION",
    "PAYLOAD_PRIOR_CONTEXT",
    "PAYLOAD_TRACE_ID",
    "PAYLOAD_MISSION_ID",
]
