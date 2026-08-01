"""TenantContext behaviour (ADR 0040 §3): a tenant is required, specific, and immutable."""

from dataclasses import FrozenInstanceError

import pytest
from pipeline_contracts import KnowledgeScope, TenancyError, TenantContext


def test_minimal_context_needs_only_a_tenant_id():
    ctx = TenantContext(tenant_id="org_acme")
    assert ctx.tenant_id == "org_acme"
    assert ctx.principal_id == ""
    assert ctx.roles == ()
    assert ctx.region == ""


def test_roles_are_normalized_to_an_immutable_tuple():
    ctx = TenantContext(tenant_id="org_acme", roles=["admin", "auditor"])
    assert ctx.roles == ("admin", "auditor")
    assert ctx.has_role("auditor")
    assert not ctx.has_role("owner")


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_absent_tenant_fails_closed(bad):
    with pytest.raises(TenancyError):
        TenantContext(tenant_id=bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("wildcard", ["*", "all", "ALL", "Any", "none", "null"])
def test_wildcard_tenant_is_rejected(wildcard):
    # A wildcard tenant is the "everything" escape hatch ADR 0040 forbids by construction.
    with pytest.raises(TenancyError):
        TenantContext(tenant_id=wildcard)


def test_same_tenant_compares_only_the_organization():
    a = TenantContext(tenant_id="org_acme", principal_id="u1")
    b = TenantContext(tenant_id="org_acme", principal_id="u2", roles=("admin",))
    c = TenantContext(tenant_id="org_globex", principal_id="u1")
    assert a.same_tenant(b)
    assert not a.same_tenant(c)


def test_context_is_frozen():
    ctx = TenantContext(tenant_id="org_acme")
    with pytest.raises(FrozenInstanceError):
        ctx.tenant_id = "org_globex"  # type: ignore[misc]


def test_to_dict_is_plain_json():
    ctx = TenantContext(tenant_id="org_acme", principal_id="u1", roles=("admin",), region="ksa")
    assert ctx.to_dict() == {
        "tenant_id": "org_acme",
        "principal_id": "u1",
        "roles": ["admin"],
        "region": "ksa",
    }


def test_two_scopes_only():
    assert {s.value for s in KnowledgeScope} == {"global", "organization"}
