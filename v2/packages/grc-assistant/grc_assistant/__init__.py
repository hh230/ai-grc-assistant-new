"""Rasheed V2 **GRC Assistant** — the product composition root (ADR 0046).

Wires the already-frozen **Execution Platform** (`tool-registry` + `pipeline-tool`'s
`RegistryExecutor` + `PipelineTool`) into the Assistant, so Mission steps run **real tools** through
the Tool Registry instead of the reference `EchoExecutor`. Composition only — no new domain, no
port, no tool; it changes nothing in the Core, the Mission layer, or the Assistant.

    from assistant_runtime import build_assistant
    from grc_assistant import build_tool_backed_mission_runtime
    from pipeline_tool import PipelineTool
    from tool_registry import ToolRegistry

    registry = ToolRegistry(); registry.register(PipelineTool(orchestrator))
    assistant = build_assistant(build_tool_backed_mission_runtime(registry))
"""

from grc_assistant.assembly import (
    build_grc_orchestrator,
    build_grc_tool_registry,
    build_tool_backed_mission_runtime,
)

__all__ = [
    "build_tool_backed_mission_runtime",
    "build_grc_tool_registry",
    "build_grc_orchestrator",
]
