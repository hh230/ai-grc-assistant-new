"""ToolRegistry (CLAUDE.md §10; ADR 0042 §9): a pure catalog — register, version, discover,
resolve. No authorization, and it resolves but never invokes."""

import pytest
from tool_registry import ToolAlreadyRegistered, ToolNotFound

from .conftest import make_tool


def test_register_and_resolve_latest(registry):
    registry.register(make_tool("map_frameworks", 1))
    registry.register(make_tool("map_frameworks", 2))
    tool = registry.get("map_frameworks")
    assert tool.spec.version == 2  # latest by default


def test_pinned_version_resolves_exactly(registry):
    registry.register(make_tool("map_frameworks", 1))
    registry.register(make_tool("map_frameworks", 2))
    assert registry.get("map_frameworks", version=1).spec.version == 1


def test_duplicate_name_version_is_rejected(registry):
    registry.register(make_tool("t", 1))
    with pytest.raises(ToolAlreadyRegistered):
        registry.register(make_tool("t", 1))


def test_unknown_tool_is_not_found(registry):
    with pytest.raises(ToolNotFound):
        registry.get("does_not_exist")


def test_unknown_version_is_not_found(registry):
    registry.register(make_tool("t", 1))
    with pytest.raises(ToolNotFound):
        registry.get("t", version=9)


def test_versions_lists_all_ascending(registry):
    registry.register(make_tool("t", 2))
    registry.register(make_tool("t", 1))
    assert registry.versions("t") == (1, 2)
    assert registry.versions("unknown") == ()


def test_contains_by_name(registry):
    registry.register(make_tool("t", 1))
    assert "t" in registry
    assert "other" not in registry


def test_discovery_returns_latest_spec_per_tool_name_sorted(registry):
    registry.register(make_tool("b_tool", 1))
    registry.register(make_tool("a_tool", 1))
    registry.register(make_tool("a_tool", 2))
    specs = registry.list_tools()
    assert [s.qualified_name for s in specs] == ["a_tool.v2", "b_tool.v1"]


# --- pure catalog: metadata is stored, never enforced -----------------------------------

def test_required_roles_are_carried_as_inert_metadata(registry):
    # `required_roles` is declarative metadata for a future authorization phase. The Registry
    # stores and exposes it — and resolves the tool to everyone, because it enforces nothing.
    registry.register(make_tool("delete_control", 1, required_roles=("admin",)))
    tool = registry.get("delete_control")
    assert tool.spec.required_roles == ("admin",)


def test_discovery_lists_every_tool_regardless_of_declared_roles(registry):
    registry.register(make_tool("public", 1))
    registry.register(make_tool("admin_only", 1, required_roles=("admin",)))
    assert {s.name for s in registry.list_tools()} == {"public", "admin_only"}


def test_registry_exposes_no_authorization_surface(registry):
    # There is no RBAC engine / permission evaluator here (a future phase owns that).
    for authz_method in ("require_access", "_may_access", "check_access", "authorize"):
        assert not hasattr(registry, authz_method)


def test_registry_resolves_but_does_not_invoke(registry, tenant):
    # The Registry hands back a Tool; invoking it is the caller's job (ADR 0042 §5). Proof the
    # resolved tool is callable, but the Registry itself never called it and cannot.
    registry.register(make_tool("echo", 1))
    tool = registry.get("echo")
    result = tool.invoke({"q": "hi"}, tenant)  # the *caller* invokes, with its own tenant
    assert result == {"echo": {"q": "hi"}, "tenant": "org_acme"}
    assert not hasattr(registry, "invoke")  # the Registry exposes no execution surface
