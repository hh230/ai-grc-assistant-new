"""The P1 loop, end to end: a customer document is ingested at runtime and becomes retrievable —
scoped to the tenant that uploaded it, invisible to any other. Uses the real `knowledge-importer`
chunker and a real `search-tools` local search over the tenant knowledge base."""

from __future__ import annotations

import pytest
from knowledge_runtime import TenantKnowledgeBase, ingest_document
from pipeline_contracts import KnowledgeScope, TenantContext
from search_tools import build_local_search_tool
from tool_registry import PAYLOAD_INSTRUCTION, ToolStepResult

_ACME = TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))
_GLOBEX = TenantContext(tenant_id="org_globex", principal_id="u9", roles=("analyst",))

_POLICY = (
    "Acme Access Control Policy. All administrator accounts must use hardware security keys "
    "for multi-factor authentication. Shared administrator credentials are prohibited."
)


def _search(kb: TenantKnowledgeBase, tenant: TenantContext, query: str) -> ToolStepResult:
    tool = build_local_search_tool(kb.keyword_provider())
    return ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: query}, tenant))


def test_ingest_produces_tenant_scoped_citable_chunks() -> None:
    kb = TenantKnowledgeBase()
    chunks = ingest_document(
        kb, _POLICY, tenant=_ACME, document_id="doc-acme-1", source_filename="acme-policy.txt"
    )
    assert len(chunks) >= 1 and len(kb) == len(chunks)
    for c in chunks:
        assert c.scope_kind is KnowledgeScope.ORGANIZATION
        assert c.organization_id == "org_acme"
        assert c.source_filename == "acme-policy.txt"
        assert c.code                                   # a hard locator → survives citation gate


def test_ingested_document_is_retrievable_for_its_tenant() -> None:
    kb = TenantKnowledgeBase()
    ingest_document(
        kb, _POLICY, tenant=_ACME, document_id="doc-acme-1", source_filename="acme-policy.txt"
    )
    result = _search(kb, _ACME, "hardware security keys")
    assert result.ok
    assert "hardware security keys" in result.output    # the customer's own content came back
    assert result.source_ids


def test_another_tenant_can_never_see_the_ingested_document() -> None:
    # org_globex uploads nothing; querying finds none of org_acme's data — base holds only acme's.
    kb = TenantKnowledgeBase()
    ingest_document(
        kb, _POLICY, tenant=_ACME, document_id="doc-acme-1", source_filename="acme-policy.txt"
    )
    result = _search(kb, _GLOBEX, "hardware security keys")
    # fail-closed (the engine's defence-in-depth refuses an out-of-scope chunk) — never a leak.
    assert result.ok is False
    assert "org_acme" not in result.output
    assert result.source_ids == ()


def test_two_tenants_documents_stay_isolated_in_one_base() -> None:
    kb = TenantKnowledgeBase()
    ingest_document(kb, _POLICY, tenant=_ACME, document_id="d1", source_filename="acme.txt")
    ingest_document(
        kb, "Globex backup policy: nightly encrypted backups retained 90 days.",
        tenant=_GLOBEX, document_id="d2", source_filename="globex.txt",
    )
    # each tenant retrieves its OWN content
    acme_own = _search(kb, _ACME, "hardware security keys")
    assert acme_own.ok and "hardware security keys" in acme_own.output
    globex_own = _search(kb, _GLOBEX, "encrypted backups")
    assert globex_own.ok and "encrypted backups" in globex_own.output
    # neither can reach the OTHER's content: querying the other's terms is fail-closed, never a leak
    crossed = _search(kb, _ACME, "encrypted backups")   # would match globex's out-of-scope chunk
    assert crossed.ok is False
    assert "encrypted backups" not in crossed.output


@pytest.mark.parametrize("query", ["hardware security keys", "administrator accounts"])
def test_ingested_content_matches_expected_queries(query: str) -> None:
    kb = TenantKnowledgeBase()
    ingest_document(kb, _POLICY, tenant=_ACME, document_id="d", source_filename="p.txt")
    assert _search(kb, _ACME, query).ok
