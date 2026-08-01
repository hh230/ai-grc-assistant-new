"""The assembler wires the real `RegistryExecutor`, not the reference `EchoExecutor` (no DB)."""

from __future__ import annotations

from grc_assistant import build_tool_backed_mission_runtime
from mission_engine import EchoExecutor
from pipeline_tool import RegistryExecutor
from tool_registry import ToolRegistry


def test_assembler_wires_the_registry_executor_not_echo() -> None:
    # an empty registry is fine here: the executor only resolves a tool at execute time, and we
    # never execute — we only check *which* executor the MissionRuntime was given.
    runtime = build_tool_backed_mission_runtime(
        ToolRegistry(), missions_table="m_test", outbox_table="o_test"
    )
    assert isinstance(runtime._executor, RegistryExecutor)  # the real tool-backed executor
    assert not isinstance(runtime._executor, EchoExecutor)
