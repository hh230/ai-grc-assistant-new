# pipeline-tool

Rasheed V2 **Pipeline Tool** (Phase 15, step 3) — the first Tool in the system, and the first
**vertical slice** ([ADR 0042](../../../docs/adr/0042-v2-mission-engine.md)).

It closes the loop from a Mission all the way to a grounded answer, reusing the existing
platform unchanged:

```
Mission → ExecutionPort → RegistryExecutor → Tool Registry → PipelineTool → AI Orchestrator → Answer
```

## What's here

- **`PipelineTool`** — a `Tool` (satisfies the tool-registry `Tool` protocol) whose single job
  is to run the existing **AI Orchestrator** (ADR 0038) as a registered capability. It maps a
  tool payload to a `UserRequest`, runs the pipeline via an injected `PipelineRunner`, and maps
  the `PipelineResult` back to the plain tool boundary (answer text, source ids, confidence,
  status, warnings). It is `READ_ONLY` — answering a grounded question changes no state — and it
  reasons about nothing; all intelligence stays in the Orchestrator and the engines beneath it.
- **`PipelineRunner`** — the narrow port the tool depends on (one method, `run`). The real
  `AIOrchestrator` satisfies it structurally, so tests drive the real pipeline behind fakes.
- **`RegistryExecutor`** — the bridge that implements the Mission Engine's `ExecutionPort` by
  **resolving a step to a Tool via the Tool Registry and invoking it** (ADR 0042 §5, §12.3). The
  Mission Engine dispatches a `StepRequest`; this executor resolves the tool, invokes it with the
  step's tenant, and maps the result to a `StepResult`. For this first slice every step routes to
  the Pipeline Tool.
- **`ToolStepResult`** — the **explicit, shared contract** every mission-invokable Tool speaks
  (`ok`, `output`, `source_ids`, `confidence`, `warnings`). The tool builds one; the executor
  maps it to a `StepResult`. Because the contract is single-sourced (not an implicit dict shape),
  **a new Tool — SQL, Document, Risk, Workflow — is added by registering it and pointing
  `tool_name` at it, with no change to `RegistryExecutor`.** The contract is deliberately
  mission-agnostic (it imports no `mission_engine`), so a Tool stays callable by any of the six
  callers, not just missions.

## Why this is only a composition package

It adds **no new domain**. It wires four existing pieces together (Mission Engine, Tool Registry,
AI Orchestrator, contracts) and imports **no LLM SDK** — the LLM-facing edge is isolated to the
one `PipelineTool` class, which holds the Orchestrator dependency. The `RegistryExecutor` knows
only the two ports (mission-engine, tool-registry); it does not import the Orchestrator, so the
bridge stays swappable. Both facts are enforced by `tests/test_architecture.py`.

## Usage

```python
from ai_orchestrator import AIOrchestrator
from mission_engine import MissionEngine, InMemoryMissionStore
from tool_registry import ToolRegistry
from pipeline_tool import PipelineTool, RegistryExecutor

registry = ToolRegistry()
registry.register(PipelineTool(orchestrator))        # orchestrator: a wired AIOrchestrator

engine = MissionEngine(InMemoryMissionStore(), RegistryExecutor(registry))
mission = engine.run_simple("goal", tenant, "What controls does the PDPL require?")
assert mission.status.value == "completed"
answer = mission.step_results[0].output
```

## Scope note — tenancy

The tenant flows `Mission → StepRequest → PipelineTool.invoke(payload, tenant)` as the invocation
contract (ADR 0040 §5). Threading it *into the pipeline itself* — making `TenantContext` a
required field on `UserRequest` and stamping `mission_id`/`tenant_id` onto the shared
`AuditRecord`/`DomainEvent` (ADR 0042 §12.2) — is the **ADR-0040 tenancy activation**, a distinct
platform-wide change (it updates every pipeline caller in one change). Until it lands, the
pipeline remains single-corpus and tenant-blind, exactly as ADR 0040 describes today's V2.

## Tests

```
uv run pytest
```

The slice test drives the **real** pipeline (real DecisionEngine, RetrievalEngine, ContextBuilder,
PromptOrchestrator; only search and generation are fakes), so a Mission completing with a grounded
answer is a genuine end-to-end proof, not a mock. `mypy --strict` clean.
