"""The local (keyword) search tool over the real engine: it finds lexical matches, returns them
cited with provenance, and — the load-bearing property — is strictly tenant-isolated."""

from __future__ import annotations

from pipeline_contracts import TenantContext
from search_tools import LOCAL_SEARCH_TOOL, build_local_search_tool
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, Tool, ToolStepResult


def _search(tool, tenant: TenantContext, query: str) -> ToolStepResult:
    return ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: query}, tenant))


def test_it_is_a_read_only_registry_tool(keyword_provider) -> None:
    tool = build_local_search_tool(keyword_provider)
    assert isinstance(tool, Tool)
    assert tool.spec.name == LOCAL_SEARCH_TOOL
    assert tool.spec.side_effect is SideEffectProfile.READ_ONLY


def test_finds_lexical_matches_with_citations_and_provenance(keyword_provider, tenant) -> None:
    result = _search(build_local_search_tool(keyword_provider), tenant, "access control")
    assert result.ok
    assert "access control" in result.output           # the snippet came back
    assert "c1" in result.source_ids                    # matched chunk id = provenance
    assert result.confidence is not None


def test_empty_query_fails_safe(keyword_provider, tenant) -> None:
    result = _search(build_local_search_tool(keyword_provider), tenant, "   ")
    assert result.ok is False
    assert "no search query" in result.warnings[0]


def test_a_query_with_no_hits_is_a_clean_empty_result(keyword_provider, tenant) -> None:
    result = _search(build_local_search_tool(keyword_provider), tenant, "zzzzquux")
    assert result.ok is True
    assert result.source_ids == ()


def test_search_never_leaks_another_tenants_data(keyword_provider_with_foreign, tenant) -> None:
    # If a provider ever admitted an out-of-scope chunk, the engine's defence-in-depth (ADR 0040 §4)
    # refuses to proceed; the tool turns that into a fail-safe ok=False. Either way the foreign
    # tenant's data NEVER reaches the caller. (In production the PgVectorProvider scopes in SQL, so
    # this path is graceful; the in-memory provider is fail-closed.)
    tool = build_local_search_tool(keyword_provider_with_foreign)
    result = _search(tool, tenant, "access control")   # tenant = org_acme
    assert result.ok is False
    assert "foreign" not in result.source_ids          # org_globex's data never surfaces (§20)
    assert "tenant isolation" in result.warnings[0]
