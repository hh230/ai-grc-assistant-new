# ADR 0047: Risk Assessment capability (MVP) — the first *composite* Assistant capability

- Status: **Accepted — architecture** (two review rulings applied 2026-07-17: the Capability is
  detection-agnostic, and the plan uses **domain** step names; implementation follows). This ADR
  itself writes no code.
- Date: 2026-07-17
- Deciders: Product Owner (review pending), Architecture
- Related: **ADR 0046 (AI GRC Assistant — the Capability/Mission Catalog this registers into)**,
  0042 (Mission Engine — composite plans), 0044 (Human Approval — *deferred* here), 0043 (Mission
  Store); the `assistant-runtime` package (`builtin/`)

> **This is the first *capability ADR*** — a deliberately **short** format (goal · inputs · outputs ·
> the Mission it creates · MVP non-goals). Every future capability (Vendor Review, ISO Controls,
> Policy Generation) follows this same short template, so each is built with the Core's discipline
> without an ADR 0046-sized document each time.

---

## Context

The Assistant runs (ADR 0046); its first built-in capability — **Simple Question** — proved the loop
`User → AssistantRuntime → Capability → Mission → MissionRuntime → Response` with a *single* read-only
step (Slice 3). **Risk Assessment is the first *composite* capability** — a multi-step Mission —
chosen to prove the Assistant can drive **more than a single question**. It is intentionally an
**MVP**: it exercises the multi-step *shape* end to end, **not** real risk analysis (which needs the
real `ExecutionPort` / tools, out of scope until the Core executor build).

---

## Decision — the five questions

**1. Goal.** Let a user ask for a risk assessment of a *subject* (an asset, vendor, system, or
scenario) and get back a **structured, multi-step risk summary** produced as a governed Mission. The
MVP goal is to prove the Assistant drives a **composite** Mission front to back — *not* to produce a
defensible risk score yet.

**2. Inputs.** Minimal: the **subject to assess**, carried as `{"request": <text>}` from the
recognizer (the free-text ask, e.g. "assess the risk of vendor X"). `input_schema = ("request",)`.
Structured inputs (category, scope, asset id, likelihood/impact factors) are **deferred** — a real
recognizer extracts them later.

**3. Outputs.** A completed **`risk_assessment` Mission** whose `step_results` carry the three
domain stages' outputs (collect_context → assess_risk → generate_report). In the MVP the steps run on the reference
`EchoExecutor`, so the "summary" is a **structural placeholder, not a computed score** — the output
*contract* is "a multi-step Mission record ending in a summary step," with real content arriving when
the executor/tools land. The `AssistantResponse` carries the Mission (the source of truth), as for
every capability (ADR 0046 §6).

**4. The Mission it creates.** A **composite** Mission type `risk_assessment` — a plan factory
`(inputs, tenant) → (goal, Plan)` producing a **3-step, non-consequential** plan:

```
Risk Assessment
  1. collect_context    (read-only)   ← domain step, not an implementation step
  2. assess_risk        (read-only)
  3. generate_report    (read-only)
```

**Domain step names, not implementation names** (review ruling): the steps are named for the GRC
*domain* (`collect_context` / `assess_risk` / `generate_report`), so they stay correct even if the
implementation changes completely later. No `consequential` steps → **no human gate** in the MVP;
`execution_profile` is `composite` (>1 step). It is registered in the Mission Catalog; the
product-facing **`risk_assessment` Capability** resolves to it.

**The Capability knows nothing about how it is detected** (review ruling — the load-bearing point of
this ADR). Selection stays strictly `Intent → Capability id → Capability Catalog`:

- the recognizer emits a **capability *intent*** — `{ "intent": "risk_assessment", "confidence": 0.93 }`
  — **never** a keyword, a rule, or a recognizer-specific token;
- the `CapabilitySelector` maps that intent id to the registered Capability (else falls back to `ask`);
- the **Capability record carries no detection field** (no keyword, no recognizer type). The
  reference `KeywordIntentRecognizer` keeps its keyword→id map **in its own config**, not on the
  Capability. Swapping the recognizer for an **LLM / semantic-search / rules / hybrid** implementation
  therefore changes **no Capability** — the whole reason detection is kept out of the Capability.

Risk Assessment is the first capability that is *not* the fallback, so the first whose intent a
recognizer must actually produce; but *how* the recognizer produces it is entirely the recognizer's
concern.

**5. Out of scope (MVP — explicitly deferred).**
- **Human Approval / gates** — the real Risk Assessment will gate report sign-off (a `consequential`
  step, ADR 0044); the MVP has none.
- **Real evaluation / scoring** — no scoring engine, rules, or LLM; steps echo (reference executor).
- **Integrations** — no vendor APIs, external databases, files, or connectors (that is the real
  `ExecutionPort` + Tool Registry, a later Core build).
- **Retrieval / grounding / citations / confidence** — deferred with the real executor.
- **Multiple Missions / orchestration** — one Mission, not several.
- **Rich structured input/output schemas** — MVP takes free text, returns a Mission record.

---

## Consequences

**Positive**
- Proves the Assistant drives a **multi-step (composite)** Mission end to end, on the tested Slice-3
  foundation — a bigger step than Simple Question, with **zero new plumbing** (just a new Capability
  + Mission type in the catalogs, plus one recognizer keyword).
- Establishes the **capability-ADR pattern** for Vendor Review, ISO Controls, Policy Generation.

**Negative / costs**
- The MVP produces **no real risk analysis** — a skeleton until the executor/tools land. Any consumer
  must understand it is a wiring/shape proof, not a product-grade assessment.
- The real Risk Assessment will later add a **gated** report step (ADR 0044) and real evaluation,
  changing the plan shape — a **new capability revision**, not a Core change.

## Alternatives considered

- **Start with a gated (approval) Risk Assessment.** Rejected for the MVP: it couples the first
  composite capability to the approval flow. Prove multi-step first; add the gate next.
- **Build real scoring now.** Rejected: needs the real `ExecutionPort`/tools (out of scope); would
  block the wiring proof on a large Core build.
- **Skip the ADR and just code it.** Rejected: the project decides-then-builds; a short capability
  ADR keeps every capability at the Core's bar.

## Implementation Status

**✅ Implemented (green; pending freeze review).** Built as `assistant_runtime/builtin/risk_assessment.py`:
- `RISK_ASSESSMENT_MISSION_TYPE` — a plan factory building a **composite, non-consequential** plan of
  the domain steps `collect_context → assess_risk → generate_report`; `RISK_ASSESSMENT_CAPABILITY`
  (id `risk_assessment`) resolving to it. **The Capability carries no detection field** — a test
  locks its fields to exactly `id/name/description/input_schema/resolver`.
- The `risk → risk_assessment` mapping is **recognizer config** in `default_intent_recognizer` (the
  reference `KeywordIntentRecognizer`), never on the Capability.
- **Verified:** composite plan with the three domain step names (no gate); **selection by intent id**
  proven with a non-keyword recognizer (swapping the recognizer changes no Capability); full loop
  in-memory and **E2E on real PostgreSQL** (3-step mission, persisted). 31 assistant-runtime tests
  green (whole V2 layer 240); `ruff` + `mypy --strict` clean.
- **Deferred (as designed):** real evaluation/scoring, tools, integrations, human gate — a later
  capability revision on the real `ExecutionPort`.
