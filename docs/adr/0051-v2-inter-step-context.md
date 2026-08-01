# ADR 0051: Inter-step context — an additive `StepRequest.prior_results` (amends ADR 0042)

- Status: **Accepted — implemented** (2026-07-20)
- Date: 2026-07-20
- Deciders: Product Owner (full authority granted), Architecture
- Related: **ADR 0042 (Mission Engine — `StepRequest`/`StepResult`, the drive loop; this ADR amends
  them)**, ADR 0048 (per-step tool), ADR 0049 (tool-step contract); `pipeline-tool`
  (`RegistryExecutor`), `llm-tools` (`generate_text`); the real composite capabilities
  (Risk Assessment, Policy Generator, Vendor Review) are the consumers this unblocks.

---

## Context

The composite capabilities are "real" (each step runs a real tool) but **not coherent**: mission steps
run **independently** — the engine builds each `StepRequest` from its `PlanStep` alone, so a later step
cannot see an earlier step's output. Concretely, Risk Assessment's `generate_report` does not read
`assess_risk`; Policy Generator's `draft_policy` does not read the `identify_controls` result; Vendor
Review's `assess_vendor` does not read the supplier controls. The product review flagged this as the
**single biggest gap** — the composites produce three disconnected artifacts, not one built-up
deliverable.

This is exactly the "necessary Core change with an ADR" the freeze rules reserve for a real need, and a
real capability now requires it. The gap is one missing piece of data: **a step must be able to see the
results of the steps before it.**

## Decision

Thread the mission's completed step results into each step's execution — **additive and
backward-compatible by construction** (empty for the first step / single-step missions).

1. **`StepRequest.prior_results: tuple[StepResult, ...] = ()`** (new field, `mission-engine`). The
   results of every step already completed in this mission, in order. Defaults empty, so a first step
   and every single-step mission are unchanged. `StepRequest` is **transient** (built per execution,
   never persisted) — so there is **no store/codec change, no schema migration, no payload-version
   bump** (unlike ADR 0044/0048).

2. **The engine populates it** (`mission-engine`). In the drive loop, `prior_results=tuple(
   mission.step_results)` when building the `StepRequest` — one line. The engine still inspects nothing
   (§3); it only carries the accumulated results across the seam.

3. **`RegistryExecutor` renders prior results into the payload** (`pipeline-tool`). It writes a readable
   "prior context" string under a new payload key `PAYLOAD_PRIOR_CONTEXT`. Because a *leaf* synthesis
   tool must read it without depending on the LLM-facing `pipeline-tool`, the key is **generic
   tool-step input** and so lives in `tool-registry` beside `PAYLOAD_INSTRUCTION` (the same reasoning as
   ADR 0049), re-exported from `pipeline-tool` for its own consumers. A tool that ignores the key
   behaves **exactly as today** — full backward compatibility.

4. **`generate_text` consumes it** (`llm-tools`). When `PAYLOAD_PRIOR_CONTEXT` is present, the LLM tool
   includes it as a context block before the user prompt — so a **synthesis** step generates *from* the
   prior steps' output. This is the clean division of labour the composites will use: **gather** steps
   (grounded: `run_pipeline` / `search` / `framework_control_library`) produce evidence; **synthesis**
   steps (`generate_text`) read that evidence via prior context and produce the deliverable.

**Net amendment:** one optional field on the transient `StepRequest`, one engine line, one executor
render, one tool read — all additive, all backward-compatible, **no persistence change**. Grounding is
preserved: the evidence still comes from the grounded gather steps; the synthesis step only *reads* it.

## Out of scope / deferred

- **`run_pipeline` consuming prior context** — the Pipeline Tool stays a self-contained grounded
  retrieve→generate on its own query (injecting prior text into RAG retrieval is a separate concern).
  Synthesis-from-prior is `generate_text`'s job.
- **A typed inter-step data contract** beyond the rendered string (structured hand-off schemas) — later.
- **Fan-out / DAG plans** — steps remain a linear sequence; `prior_results` is all steps before this one.

## Consequences

**Positive** — the composites become **coherent**: the report is written from the assessment, the policy
draft from the identified controls, the vendor assessment from the supplier controls. Unblocks the whole
"connect the steps" product need with a minimal additive change. **Negative** — amends the frozen
`StepRequest` (ADR 0042); real but scoped to one optional, transient field and its pass-through. A step
now may receive large prior context; tools bound it (the LLM tool already carries `max_output_tokens`,
and the rendered context can be truncated).

## Implementation Status

**Implemented (2026-07-20).** `StepRequest.prior_results` + engine pass-through (`mission-engine`);
`PAYLOAD_PRIOR_CONTEXT` + executor render (`pipeline-tool`); `generate_text` consumption (`llm-tools`),
each with tests. Then the composite capabilities are rewired to gather→synthesize (a capability change,
no ADR) and proven coherent end to end in `grc-assistant`.
