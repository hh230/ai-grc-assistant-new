# tool-registry

Rasheed V2 **Tool Registry** (Phase 15, step 2) — the central catalog of every business
capability ([CLAUDE.md §10](../../../CLAUDE.md), [ADR 0042](../../../docs/adr/0042-v2-mission-engine.md) §9).

> **The Registry is a pure catalog, and knows nothing about execution.** It registers,
> versions, discovers, and **resolves** a `Tool` for a caller — it never *invokes* one, never
> touches a mission, an agent, or the pipeline, and neither imports nor is imported by the
> Mission Engine. It performs **no authorization**: there is no RBAC engine, permission
> evaluator, or policy framework here — that is a future phase. This decoupling is fixed in
> ADR 0042 §5/§9 and enforced by a purity test.

## What it is

- **`ToolSpec`** — a tool's catalog entry: `name`, `version`, `description`, `side_effect`
  (`READ_ONLY` | `CONSEQUENTIAL`), `required_roles`, and cost/latency planning hints. Immutable
  and versioned: a breaking change is a new version (`map_frameworks.v2`), never a mutation.
  A tool only *declares* `CONSEQUENTIAL`; the **Mission Engine enforces the human gate**, not
  the tool (a tool never self-authorizes). `required_roles` is likewise **declarative metadata
  only** — a future authorization phase reads it; the Registry never evaluates it.
- **`Tool`** — the capability contract (a `Protocol`): a `spec` plus `invoke(payload, tenant)`.
  A tool is invoked with a `TenantContext` (CLAUDE.md §9) — by the *caller*, not the Registry.
- **`ToolRegistry`** — a **pure catalog**: register / resolve (latest or pinned version) /
  discover / version-list. It performs **no authorization** — it resolves and lists every
  registered tool. Enforcing `required_roles` is a future phase, not this one.

## Why it does not execute

The Registry is the catalog; execution belongs elsewhere. In a later step, the executor behind
the Mission Engine's `ExecutionPort` resolves a mission step to tools **via this Registry** and
invokes them. Keeping invocation out of the Registry is what lets the Registry stay ignorant of
missions and the pipeline — and lets it land now, before either the executor or the Mission
Engine references it.

```
Mission Engine ──dispatch step──▶ ExecutionPort ──▶ [executor, step 3]
                                                        │ resolves tool
                                                        ▼
                                                   ToolRegistry.get(name) ──▶ Tool
                                                        │ caller invokes with the mission's tenant
                                                        ▼
                                                   tool.invoke(payload, tenant)
```

The Registry appears nowhere upstream of that executor. Neither this package nor `mission-engine`
imports the other.

## Usage

```python
from tool_registry import ToolRegistry, ToolSpec, SideEffectProfile

registry = ToolRegistry()
registry.register(my_tool)              # my_tool.spec = ToolSpec(name="map_frameworks", version=1)

tool = registry.get("map_frameworks")   # latest version (or version=N to pin)
specs = registry.list_tools()           # discovery — every registered tool, for the Orchestrator to plan
```

Registration is the **plugin entry point** (CLAUDE.md §17): a new capability appears in the
platform by registering here — no core change.

## Architecture & dependencies

```
tool-registry ─→ pipeline-contracts   (TenantContext — pure)
```

Pure domain: no database, no LLM SDK, no framework, and — enforced by `tests/test_purity.py` —
no `mission_engine` and no execution/eventing layer. `mypy --strict` clean.

## Tests

```
uv run pytest
```

Covers spec validity/versioning, register/resolve (latest + pinned), duplicate rejection,
discovery, version listing, `required_roles` carried as inert metadata (the Registry exposes no
authorization surface), and the "resolves but never invokes" guarantee.
