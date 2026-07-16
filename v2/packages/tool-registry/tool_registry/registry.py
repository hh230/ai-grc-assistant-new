"""The Tool Registry (CLAUDE.md §10; ADR 0042 §9).

The central catalog of every capability the platform can perform: **register, discover, and
version** tools. It is the single source of truth for what the platform can *do* — nothing
calls a capability "out of band."

**It is a pure catalog of tools and metadata.** It resolves a `Tool` by name and version and
lists what exists — nothing more. It performs **no authorization**: there is no RBAC engine,
no permission evaluator, and no policy framework here. A tool's `required_roles` is carried as
*declarative metadata* (CLAUDE.md §10) that a **future authorization phase** will read and
enforce; the Registry stores it and never evaluates it. Authorization belongs to that later
phase, not to the catalog.

**It knows nothing about execution or missions.** The Registry resolves a `Tool`; it never
invokes one, never touches a mission, an agent, or the pipeline, and neither imports nor is
imported by the Mission Engine. This decoupling (fixed in ADR 0042 §5, §9) is what lets the
executor — a later step behind the Mission Engine's `ExecutionPort` — be the one that resolves
a step to tools via this Registry and invokes them, without the Registry ever depending on any
of that.

This first implementation is an in-process catalog. A different backing (a distributed
registry, a plugin loader) can implement the same surface later; registration is the plugin
entry point (CLAUDE.md §17) — a new tool appears by registering here, with no core change.
"""

from __future__ import annotations

from tool_registry.errors import ToolAlreadyRegistered, ToolNotFound
from tool_registry.spec import ToolSpec
from tool_registry.tool import Tool


class ToolRegistry:
    """An in-process catalog keyed by tool name and version. A pure catalog: it registers,
    resolves, and lists tools and their metadata — it does not invoke tools and does not
    authorize callers."""

    def __init__(self) -> None:
        self._by_name: dict[str, dict[int, Tool]] = {}

    # --- registration (the plugin entry point) ------------------------------------------

    def register(self, tool: Tool) -> None:
        """Add a tool to the catalog. Registering a name+version that already exists is
        rejected — a breaking change ships as a new version (CLAUDE.md §10)."""
        spec = tool.spec
        versions = self._by_name.setdefault(spec.name, {})
        if spec.version in versions:
            raise ToolAlreadyRegistered(f"{spec.qualified_name} is already registered")
        versions[spec.version] = tool

    # --- resolution & discovery ---------------------------------------------------------

    def get(self, name: str, *, version: int | None = None) -> Tool:
        """Resolve a tool by name. `version=None` returns the latest; a pinned version is
        returned exactly. This is a catalog lookup only — it applies no authorization (that is
        a future phase); the caller invokes the resolved tool with its own tenant."""
        versions = self._by_name.get(name)
        if not versions:
            raise ToolNotFound(f"no tool named {name!r} is registered")
        resolved = version if version is not None else max(versions)
        tool = versions.get(resolved)
        if tool is None:
            raise ToolNotFound(f"tool {name!r} has no version {resolved}")
        return tool

    def list_tools(self) -> tuple[ToolSpec, ...]:
        """Discovery: the spec of the latest version of every registered tool, name-sorted.
        This is the catalog the Orchestrator reads to plan a mission (CLAUDE.md §10)."""
        specs = [versions[max(versions)].spec for versions in self._by_name.values()]
        return tuple(sorted(specs, key=lambda spec: spec.qualified_name))

    def versions(self, name: str) -> tuple[int, ...]:
        """Every registered version of a tool, ascending. Empty if the tool is unknown."""
        return tuple(sorted(self._by_name.get(name, {})))

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._by_name
