# ADR 0048: Per-step tool selection — an additive `PlanStep.tool` (amends ADR 0042/0043)

- Status: **Accepted — implemented** (2026-07-20; the five additive touches below are shipped and frozen)
- Date: 2026-07-17 (accepted & implemented 2026-07-20)
- Deciders: Product Owner (review pending), Architecture
- Related: **ADR 0042 (Mission Engine — `PlanStep`, `StepRequest`, the engine; this ADR amends them)**,
  ADR 0043 (Mission Store — the plan codec; amended), 0046 (Assistant), 0047 (Risk Assessment — the
  first multi-tool capability that needs this); `tool-registry`, `pipeline-tool` (`RegistryExecutor`),
  `grc-assistant`

---

## Context

The Execution Platform exists and is now wired in (Step A): missions run their steps through
`RegistryExecutor` → `Tool Registry` → `Tool` instead of `EchoExecutor`. But **`RegistryExecutor`
routes *every* step to a *single* tool** — its constructor's `tool_name` (default `run_pipeline`).

That is fine for a **single-tool mission** (Simple Question → one grounded answer), but not for a
**multi-tool mission**. Risk Assessment (ADR 0047) is the first: its domain steps
`collect_context → assess_risk → generate_report` will, once real tools exist, run **different
tools** (read a document, search controls, analyze, generate a report). Today all three would hit the
same tool. `RegistryExecutor`'s own docstring already anticipates the fix: *"When plans name tools
explicitly (an additive `PlanStep` field in a later phase), the executor will resolve the named tool
instead."* This ADR is that phase.

The gap is one missing piece of data: **a mission step must be able to name the tool it runs.** That
data lives on the plan, so it touches the **frozen** `PlanStep` (ADR 0042) — hence an ADR.

---

## Decision

Add an **additive, optional** tool name to the step, thread it through the frozen seam, and have the
executor honour it — **backward-compatible by construction** (empty ⇒ today's single-tool behaviour).

1. **`PlanStep.tool: str = ""`** (new field, `mission-engine`). The registered tool name a step routes
   to. Empty means "use the executor's default tool" — so every existing plan is unchanged. The
   step's existing `instruction` stays the *opaque per-step payload* (the *what*); `tool` is the
   *which*. No structured tool-input schema is added here (deferred).

2. **`StepRequest.tool: str = ""`** (new field, `mission-engine`). The engine builds a `StepRequest`
   from a `PlanStep`; the executor only sees the `StepRequest`, so the tool name must ride across that
   frozen seam too. The engine copies `step.tool` into `request.tool` — one line in the drive loop.

3. **`RegistryExecutor` honours `request.tool`** (`pipeline-tool`). It resolves `request.tool` if set,
   else falls back to its constructor default — so a per-step tool overrides, and unset steps behave
   exactly as today. One small change; no new class.

4. **The plan codec round-trips `tool`** (`mission-store`). `PlanStep.to_dict()` already includes the
   new field automatically (via `dataclass_dict`); the read side gains `tool = data.get("tool", "")`
   so **old plans deserialize as `tool=""`**. Because `tool` rides inside the existing plan JSONB, there
   is **no new column and no schema migration**; and because old plans read as `""`, **no
   `payload_schema_version` bump is required** (unlike ADR 0044's nested object — this is a single
   optional scalar with a safe default).

**Net amendment:** two frozen dataclasses gain one optional field each, one engine line, one executor
line, one codec line — all additive, all backward-compatible. This is a smaller amendment than
ADR 0044, and like it, it is a **conscious change to frozen ADR 0042/0043**, named here, not smuggled.

---

## Out of scope (explicitly deferred)

- **Structured tool inputs** beyond the `instruction` string (a typed per-tool payload schema) — a
  later refinement; the instruction remains the per-step payload for now.
- **The Orchestrator planning tools** (an agent choosing tools) — planning still produces the `Plan`;
  this ADR only lets a plan *name* a tool. Automatic tool selection is a later phase.
- **Tool authorization / `required_roles` enforcement** — still declarative (ADR 0042 §5; tool-registry).
- **The real GRC tools themselves** (`read_document`, `search_controls`, …) — built next, one at a
  time, once a step can name them.
- **Multiple tools per step / fan-out** — one tool per step; orchestration across steps is the plan's.

---

## Consequences

**Positive**
- Unlocks **multi-tool missions** (Risk Assessment and every future composite GRC capability) with a
  minimal, additive amendment — no new plumbing, the Execution Platform and Mission Engine unchanged
  in shape.
- Backward-compatible: every existing plan/mission runs identically (`tool=""` ⇒ default tool).
- Keeps the routing data where it belongs — on the plan step — instead of overloading `instruction`.

**Negative / costs**
- Amends the frozen `PlanStep` and `StepRequest` (ADR 0042) and the plan codec (ADR 0043). Real, but
  scoped to one optional field and its pass-through.
- A step now carries a tool name that must match a registered tool; a typo yields a `ToolNotFound` at
  execution (fail-safe, surfaced by the mission), not a silent wrong-tool run.

## Alternatives considered

- **Encode the tool in `instruction`** (e.g. `"search_controls|<payload>"`). Rejected: pollutes the
  opaque per-step payload with routing, and every tool/executor would have to parse it. A dedicated
  field is clearer and typed.
- **A per-mission tool map** (step id → tool, outside the plan). Rejected: splits the plan's truth
  into a side table; the tool a step runs *is* part of the step.
- **Give `RegistryExecutor` the routing logic** (infer tool from the instruction/step). Rejected:
  that is planning; the plan should state the tool explicitly, deterministically.

## Implementation Status

**Implemented & frozen (2026-07-20).** The five additive touches shipped exactly as decided:

1. `PlanStep.tool: str = ""` — `mission-engine/mission_engine/plan.py`.
2. `StepRequest.tool: str = ""` — `mission-engine/mission_engine/ports.py`.
3. Engine pass-through (`request.tool = step.tool`) — `mission-engine/mission_engine/engine.py`.
4. `RegistryExecutor` honours `request.tool` (else its constructor default) —
   `pipeline-tool/pipeline_tool/executor.py`.
5. Codec round-trips `tool` (`data.get("tool", "")` on read) — `mission-store/mission_store/codec.py`.

**Tests (all green; `ruff` + `mypy --strict` clean on all three touched packages):**
- `pipeline-tool/tests/test_contract.py` — per-step tool overrides the default; empty tool falls back
  to the default; and a **composite plan routes each of `collect`/`assess`/`report` to its own tool**,
  driven end to end through the frozen `MissionEngine` (the ADR's "two-tool plan" acceptance test).
- `mission-store/tests/test_codec.py` — a per-step tool survives the plan-JSON round-trip; and a
  **legacy plan with no `tool` key deserializes as `tool=""` at the current payload version** — no
  version bump, no migration (§4 confirmed in code).

Backward compatibility verified: every pre-existing mission-engine (76) and mission-store (88) test
passes unchanged. **Next:** the real GRC tools are built one at a time, each named by a plan step.
