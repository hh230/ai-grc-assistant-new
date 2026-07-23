# ADR 0049: The shared tool-step result contract lives in `tool-registry` (additive; enables lightweight leaf tools)

- Status: **Accepted — implemented** (2026-07-20)
- Date: 2026-07-20
- Deciders: Architecture (autonomous execution mandate)
- Related: ADR 0042 (Mission Engine — `ExecutionPort`, `StepResult`), ADR 0048 (per-step tool
  selection), `tool-registry`, `pipeline-tool` (`RegistryExecutor`, `ToolStepResult`); the first
  real GRC leaf tool (ADR 0050) is the caller this unblocks.

---

## Context

Every Tool invoked as a mission step returns the **same structured result** — `ToolStepResult`
(`ok`, `output`, `source_ids`, `confidence`, `warnings`) — which `RegistryExecutor` maps to the
Mission Engine's `StepResult`. That contract is what lets *any* conforming tool (SQL, Document,
Risk, Framework Library, …) plug into the execution path with no change to `RegistryExecutor`
(established at Phase 15 step 3, ADR 0042 §5).

Today `ToolStepResult` is **defined in `pipeline-tool`**, and `pipeline-tool` hard-depends on
`ai-orchestrator` (it also ships `PipelineTool`, which wraps the AI Orchestrator). So any new
**leaf tool that speaks the contract would have to depend on `pipeline-tool`** — dragging the
entire LLM/orchestrator stack into a tool that may have nothing to do with LLMs (a control-library
lookup, a document parser). That violates CLAUDE.md §9 ("no hidden coupling … never directly on an
LLM SDK") and makes the dependency graph wrong: the contract every tool speaks sits in a heavy,
LLM-facing package instead of the pure one every tool already depends on.

`tool-registry` is that pure package — it depends only on `pipeline-contracts`, defines the `Tool`
protocol and `ToolSpec`, and declares itself to hold "no mission/agent/pipeline knowledge." A
tool's **result shape** is exactly a tool-registry-level concept and carries no mission knowledge.

## Decision

**Relocate `ToolStepResult` (and its coercion helpers) to `tool-registry`** as the canonical,
lightweight tool-result contract; `pipeline-tool` **re-exports it** so its public API is unchanged.

1. New module `tool_registry/result.py` defines `ToolStepResult` (identical shape + `as_payload`/
   `from_payload` + the safe-coercion helpers). `tool_registry.__init__` exports it. Additive —
   nothing in `tool-registry` changes; a new export appears.
2. `tool-registry` also owns the one **generic** tool-step input key, `PAYLOAD_INSTRUCTION`
   (`"instruction"`) — a leaf tool must read the step's instruction, and that key is not mission
   knowledge. The **mission-specific** envelope keys (`PAYLOAD_TRACE_ID`, `PAYLOAD_MISSION_ID`, used
   to stamp audit, ADR 0042 §12.2) stay in `pipeline-tool`. `pipeline_tool/contract.py` imports
   `ToolStepResult` and `PAYLOAD_INSTRUCTION` from `tool_registry` and **re-exports** them, so
   `from pipeline_tool import ToolStepResult` and `from pipeline_tool.contract import
   PAYLOAD_INSTRUCTION` keep working unchanged — **neutral to `pipeline-tool`'s public surface**.
3. Leaf tools depend only on `tool-registry` (+ `pipeline-contracts`) and import `ToolStepResult` and
   `PAYLOAD_INSTRUCTION` from `tool_registry` — no LLM stack, no `pipeline-tool` dependency.

**Net:** one new module + export in `tool-registry` (additive), one file in `pipeline-tool` turned
into a thin re-export (public API identical, all its tests green). Purity preserved: `tool-registry`
still knows nothing of missions, pipelines, or LLMs — a result shape is not mission knowledge.

## Why this is additive / neutral (allowed under the freeze)

- `tool-registry`: gains an export; no existing symbol changes. Additive.
- `pipeline-tool`: `ToolStepResult` is the *same class* re-exported from its new home; every import
  path and every test that referenced it still resolves. Neutral (no consumer breaks).
- No schema, no persisted shape, no `StepResult`/`PlanStep` change. This ADR does **not** touch
  ADR 0042/0043 frozen dataclasses (unlike ADR 0048).

## Out of scope / deferred

- Moving the payload-key constants or any mission-facing envelope into `tool-registry` (kept in
  `pipeline-tool` on purpose — they are mission knowledge).
- A typed per-tool **input** schema (still the opaque `instruction` string; ADR 0048 §"out of
  scope").
- Authorization / `required_roles` enforcement (still declarative).

## Consequences

**Positive** — every future leaf tool (Framework Library, PDF/DOCX/XLSX parsers, search, …) speaks
the mission-step contract by depending on the pure `tool-registry` only; the dependency graph
matches the architecture (contract in the package all tools share). **Negative** — a frozen package
(`pipeline-tool`) is edited, even if only to re-export; recorded here so it is named, not smuggled.

## Implementation Status

**Implemented (2026-07-20).** `tool_registry/result.py` added and exported; `pipeline_tool/contract.py`
re-exports it; `pipeline-tool` suite unchanged and green; `ruff` + `mypy --strict` clean on both
packages. Consumed immediately by the first real GRC leaf tool (ADR 0050).
