"""This is a composition/adapter package — it legitimately depends on several packages to wire
them together. But two rules still hold: business logic imports no LLM SDK (CLAUDE.md §22), and
the executor bridges the Mission Engine to the Registry without importing the AI Orchestrator
itself (the tool owns that dependency, not the executor)."""

import ast
from pathlib import Path

from mission_engine import ExecutionPort
from pipeline_tool import PipelineTool, RegistryExecutor

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "pipeline_tool"


def _imports(module: str) -> set[str]:
    tree = ast.parse((PACKAGE_DIR / module).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
    return names


def test_no_llm_sdk_is_imported_in_business_logic():
    for source in PACKAGE_DIR.rglob("*.py"):
        assert not (_imports(source.name) & {"openai", "anthropic", "google", "cohere"}), (
            f"{source.name} imports an LLM SDK directly"
        )


def test_executor_does_not_import_the_orchestrator_or_pipeline():
    # The executor only knows the two ports (mission-engine, tool-registry). The orchestrator
    # dependency belongs to the tool it resolves, keeping the bridge swappable.
    imported = _imports("executor.py")
    assert "ai_orchestrator" not in imported
    assert imported & {"mission_engine", "tool_registry"}


def test_registry_executor_satisfies_the_execution_port(registry):
    assert isinstance(RegistryExecutor(registry), ExecutionPort)


def test_pipeline_tool_holds_the_orchestrator_dependency(orchestrator):
    # The tool is where the AI Orchestrator dependency lives — proof the slice's LLM-facing
    # edge is isolated to one class.
    assert "ai_orchestrator" in _imports("tool.py")
    assert isinstance(PipelineTool(orchestrator).spec.name, str)


def test_tool_and_contract_are_mission_agnostic():
    # A Tool must be invokable by any of the six callers (CLAUDE.md §9), not just missions —
    # so neither the tool nor the shared result contract may depend on the Mission Engine. The
    # StepResult mapping is the executor's job alone.
    assert "mission_engine" not in _imports("tool.py")
    assert "mission_engine" not in _imports("contract.py")
