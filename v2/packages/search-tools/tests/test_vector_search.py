"""The vector (semantic) search tool over the real engine + in-memory vector provider. The stub
embedder maps a query containing `target-<id>` to that chunk's vector for deterministic ordering."""

from __future__ import annotations

from pipeline_contracts import TenantContext
from search_tools import VECTOR_SEARCH_TOOL, build_vector_search_tool
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, Tool, ToolStepResult


def _search(tool, tenant: TenantContext, query: str) -> ToolStepResult:
    return ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: query}, tenant))


def test_it_is_a_read_only_registry_tool(vector_provider) -> None:
    tool = build_vector_search_tool(vector_provider)
    assert isinstance(tool, Tool)
    assert tool.spec.name == VECTOR_SEARCH_TOOL
    assert tool.spec.side_effect is SideEffectProfile.READ_ONLY


def test_semantic_search_returns_the_targeted_chunk_first(vector_provider, tenant) -> None:
    result = _search(build_vector_search_tool(vector_provider), tenant, "target-c2 risk")
    assert result.ok
    assert result.source_ids[0] == "c2"        # the stub-embedded target ranks first
    assert result.confidence is not None


def test_empty_query_fails_safe(vector_provider, tenant) -> None:
    result = _search(build_vector_search_tool(vector_provider), tenant, "")
    assert result.ok is False
