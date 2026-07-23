# grc-assistant

Rasheed V2 **GRC Assistant** — the product composition root ([ADR 0046](../../../docs/adr/0046-v2-ai-grc-assistant.md)).
It wires the **already-frozen Execution Platform** into the Assistant so Mission steps run **real
tools** through the Tool Registry, instead of the reference `EchoExecutor`.

## The Execution Platform already exists

Phase 15 (steps 2–3) built it and froze it — nothing here re-implements it:

```
Mission → ExecutionPort → RegistryExecutor → Tool Registry → Tool → Result
```

- [`tool-registry`](../tool-registry) — `ToolRegistry`, `ToolSpec`, `Tool` (23 tests).
- [`pipeline-tool`](../pipeline-tool) — `RegistryExecutor` (implements the frozen `ExecutionPort` by
  resolving a step → Tool via the Registry and invoking it) + `PipelineTool` (the first real tool,
  wrapping the AI Orchestrator for grounded answers) (15 tests).

The only thing that was missing was **wiring it in**: `MissionRuntime` defaults to `EchoExecutor`, so
missions echoed instead of running tools.

## What this package adds (composition only)

`build_tool_backed_mission_runtime(registry, *, tool_name=…)` — a `MissionRuntime` whose
`ExecutionPort` is the real `RegistryExecutor` instead of `EchoExecutor`. That's it: no new domain, no
port, no tool; nothing changes in the Core, the Mission layer, or the Assistant. Swapping Echo for
real tools is a **constructor choice** — the payoff of the ports design.

`build_grc_tool_registry(orchestrator)` — assembles the **standard GRC tool set** into a
`ToolRegistry`: the **Pipeline Tool** (default — grounded RAG) and the **Framework Library** control
lookup (`framework-library`: bundled ISO 27001 / CIS / NIST catalogs). Capabilities name a tool by
registry name and the executor routes to it per step (`PlanStep.tool`, ADR 0048); adding a real tool
is registering it here.

```python
from assistant_runtime import build_assistant
from grc_assistant import build_grc_tool_registry, build_tool_backed_mission_runtime

registry = build_grc_tool_registry(orchestrator)       # Pipeline Tool + Framework Library
assistant = build_assistant(build_tool_backed_mission_runtime(registry))

assistant.handle("what does the PDPL say about consent?", tenant)  # → grounded pipeline answer
assistant.handle("iso controls for A.8.5", tenant)                 # → real ISO controls (ISO Controls capability)
```

## Tests

```
uv run pytest
```

- `test_wiring.py` — the assembler wires `RegistryExecutor`, not `EchoExecutor` (no DB).
- `test_grounded_e2e.py` — **the whole stack on real PostgreSQL**: the Assistant answers a Simple
  Question with a **grounded answer from the pipeline** (the real pipeline runs behind fake search +
  generation providers, so no network/SDK). DB-gated; auto-skips without a database.

## What's next (not here)

- **Per-step tool selection** — today `RegistryExecutor` routes every step to one tool. For
  multi-tool capabilities (Risk Assessment: `read → search → analyze → report`) a step must name its
  tool — an additive `PlanStep` field, decided in its own short **Core ADR**.
- **Real GRC tools** — `Read Document`, `Search Controls`, `Analyze`, `Generate Report`, each a
  `Tool` registered in the Registry.
