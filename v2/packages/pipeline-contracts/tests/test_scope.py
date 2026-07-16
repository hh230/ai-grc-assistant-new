"""RetrievalScope (ADR 0040 §2): a generic, extensible retrieval boundary — and global scope
is represented explicitly, never by an empty string."""

import pytest
from pipeline_contracts import (
    Filter,
    KnowledgeScope,
    RetrievalScope,
    TenancyError,
    TenantContext,
)


def test_organization_scope_carries_a_tenant():
    scope = RetrievalScope.for_tenant("org_acme")
    assert scope.kind is KnowledgeScope.ORGANIZATION
    assert scope.tenant_id == "org_acme"
    assert scope.includes_organization


def test_global_scope_is_explicit_never_an_empty_string():
    scope = RetrievalScope.global_only()
    assert scope.kind is KnowledgeScope.GLOBAL
    assert scope.tenant_id is None          # None, not "" — a real, named absence
    assert not scope.includes_organization


def test_derives_from_a_tenant_context():
    ctx = TenantContext(tenant_id="org_acme", principal_id="u1")
    assert RetrievalScope.from_context(ctx) == RetrievalScope.for_tenant("org_acme")


def test_organization_scope_requires_a_tenant():
    with pytest.raises(TenancyError):
        RetrievalScope(kind=KnowledgeScope.ORGANIZATION, tenant_id=None)
    with pytest.raises(TenancyError):
        RetrievalScope(kind=KnowledgeScope.ORGANIZATION, tenant_id="  ")


def test_global_scope_forbids_a_tenant():
    with pytest.raises(TenancyError):
        RetrievalScope(kind=KnowledgeScope.GLOBAL, tenant_id="org_acme")


def test_filter_carries_scope_orthogonally_to_metadata():
    f = Filter(document_profiles=("law",), scope=RetrievalScope.for_tenant("org_acme"))
    assert not f.is_empty()                 # metadata present
    # a scope-only filter still has an "empty" metadata predicate — scope is orthogonal
    scope_only = Filter(scope=RetrievalScope.for_tenant("org_acme"))
    assert scope_only.is_empty()
    assert scope_only.scope is not None


def test_scope_is_serializable():
    assert RetrievalScope.for_tenant("org_acme").to_dict() == {
        "kind": "organization",
        "tenant_id": "org_acme",
    }
