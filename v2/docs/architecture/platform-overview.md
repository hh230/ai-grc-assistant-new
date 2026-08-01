# Rasheed V2 — Platform Overview (dependency graph & layers)

- Status: **Current as of Phase 14.5** (2026-07-16). Verified against the packages'
  `pyproject.toml` dependency declarations and their imports, not drawn from memory.
- Scope: `v2/packages/` — the AI read pipeline and the scaffolding around it.
- Companions: the per-package architecture docs
  ([knowledge-library](knowledge-library.md), [chunking-engine](chunking-engine.md),
  [retrieval-engine](retrieval-engine.md), [context-builder](context-builder.md),
  [prompt-orchestrator](prompt-orchestrator.md), [decision-engine](decision-engine.md),
  [platform-hardening](platform-hardening.md)) and
  [ADR 0038](../../../docs/adr/0038-v2-pipeline-contracts-and-ai-orchestrator.md) /
  [ADR 0039](../../../docs/adr/0039-v2-platform-hardening.md) /
  [ADR 0040](../../../docs/adr/0040-v2-tenancy-model.md).

---

## 1. Layers

Dependencies point **inward and downward**. Nothing below reaches up.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  COMPOSITION ROOT                                                            │
│  ai-orchestrator — sequencing · wiring/DI · metrics · cancellation · gates   │
│  the ONLY place the concrete engines meet. No business logic lives here.     │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ calls, in order
┌───────────────────────────────▼─────────────────────────────────────────────┐
│  ENGINES  (hexagonal — each owns one capability, none knows another)         │
│                                                                              │
│   decision-engine  →  retrieval-engine  →  context-builder                   │
│   (what to do)        (what we know)       (structure the evidence)          │
│                                                                              │
│   prompt-orchestrator  →  generation-engine  →  answer-validation            │
│   (the LLMRequest)        (retry · adapters)     (the verdict)               │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ every shape that crosses a boundary
┌───────────────────────────────▼─────────────────────────────────────────────┐
│  CONTRACTS                                                                   │
│  pipeline-contracts — pure models, enums, ports, and the shared rules:       │
│    · intent_registry  (per-intent behaviour: routing · contract · ordering)  │
│    · citations        (formatting · validity gates · identity)               │
│    · generation       (the GenerationProvider port + error model)            │
│  Depends on NOTHING. stdlib only, enforced by tests/test_purity.py.          │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY  (side-channels — opt-in, depend on nothing at all)            │
│  event-bus (domain events · EventBus port · AuditRecord · AuditSink port)     │
│  pipeline-tracing (Tracer · Span · Trace)                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Why the observability layer depends on nothing — not even the contracts.** If `event-bus`
imported `pipeline-contracts`, a contract change could break the audit trail, and an event
could start carrying a whole `ContextPackage`. Events carry summary fields only (ids, counts,
provider names); the composition root maps rich artifacts down to summaries when it publishes.
That is a deliberate cut, not an oversight.

---

## 2. Dependency graph

Exactly as declared. No cycles.

```
                          ┌──────────────────┐
                          │ ai-orchestrator  │  (composition root)
                          └────────┬─────────┘
        ┌──────────┬──────────┬────┴─────┬──────────────┬───────────────┐
        ▼          ▼          ▼          ▼              ▼               ▼
  decision-   retrieval-  context-   prompt-      generation-     answer-
   engine      engine      builder   orchestrator    engine       validation
        │          │          │        │  │             │               │
        │          │          │        │  └─────────────┼───────────────┤
        │          │          │        │   (context-builder:            │
        │          │          │        │    token estimation only)      │
        └──────────┴──────────┴────────┴────────────────┴───────────────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │pipeline-contracts│  (depends on nothing)
                         └──────────────────┘

  ai-orchestrator ─────→ event-bus         ┐  observability side-channels:
  ai-orchestrator ─────→ pipeline-tracing  ┘  depend on nothing, opt-in
```

| Package | Depends on |
|---|---|
| `pipeline-contracts` | — (stdlib only) |
| `event-bus` | — |
| `pipeline-tracing` | — |
| `decision-engine` | `pipeline-contracts` |
| `retrieval-engine` | `pipeline-contracts` |
| `context-builder` | `pipeline-contracts` |
| `generation-engine` | `pipeline-contracts` |
| `answer-validation` | `pipeline-contracts` |
| `prompt-orchestrator` | `pipeline-contracts`, `context-builder` |
| `ai-orchestrator` | all of the above |

**The one non-obvious edge:** `prompt-orchestrator → context-builder`. It is *not* a layering
violation and *not* a citation dependency — it exists solely for the pure token-estimation
helper (`context_builder.budget.estimate_tokens`) used while sizing prompt segments. Until
Phase 14.5 it also borrowed `citation_is_complete` from there; that rule now comes from
`pipeline_contracts.citations` directly.

**Dev-only edges, excluded above.** Several packages ship `benchmark.py` / `examples.py`
modules that drive the *upstream* pipeline to produce realistic inputs (e.g.
`context_builder.examples` imports `retrieval_engine`; `prompt_orchestrator.benchmark`
imports `context_builder`'s engine). These are demo/benchmark harnesses, declared as
`[dependency-groups] dev`, and are not on any runtime path. The table lists runtime
dependencies.

---

## 3. The run

```
UserRequest
  → DecisionEngine        what to do          (classification lives there, not in the root)
  → RetrievalEngine       what we know        (only when the plan requires retrieval)
  → ContextBuilder        structure evidence  (citations preserved by construction)
  → PromptOrchestrator    the LLMRequest      (provider-agnostic, layered, versioned)
  → GenerationEngine      the only external call — always last
  → AnswerValidator       the verdict         (opt-in; reports, never suppresses)
→ PipelineResult (status · plan · retrieved · context · llm_request · answer · metrics
                  · warnings · validated · trace)
```

Fail-safe policies the root enforces (CLAUDE.md §16):

- an `LLMRequest` that failed validation is **never** sent to a provider;
- a plan requiring a human gate pauses before generation when a gate is configured;
- retrieval demanded but not wired degrades to explicit insufficient-evidence handling with
  a warning — never a silent guess;
- a broken event subscriber degrades to a warning; observability never breaks a run.

---

## 4. Single sources of truth

The rule that keeps the engines from drifting: where two stages must agree on something, the
something lives in `pipeline-contracts` and both read it.

| Concern | Owner | Who reads it |
|---|---|---|
| Per-intent behaviour (routing, response contract, workflow template, ordering, output profile) | `pipeline_contracts.intent_registry` | decision-engine, context-builder, prompt-orchestrator, generation |
| Citation formatting, validity, identity | `pipeline_contracts.citations` | retrieval-engine, context-builder, prompt-orchestrator, answer-validation |
| The generation port + error model | `pipeline_contracts.generation` | generation-engine (implements), ai-orchestrator (depends) |
| Serialization conventions | `pipeline_contracts.serialization` | every contract model |
| What happened in a run | `event_bus` domain events | AuditTrailBuilder, any subscriber |

Engines re-export contract names for backward compatibility (`from retrieval_engine import
Citation`, `from context_builder.citations import citation_is_complete`), but the definitions
live in one place and object identity is shared everywhere.

---

## 5. What is deliberately absent

Reading this graph, note what is *not* in it — none of it is an oversight:

- **No tenancy.** No contract carries a `tenant_id`; no filter carries a scope predicate.
  The V2 pipeline has **no tenant enforcement** and is not fit to serve two tenants' data
  today. It is single-corpus by construction, which is the only thing currently keeping that
  safe. The model is specified in [ADR 0040](../../../docs/adr/0040-v2-tenancy-model.md);
  the build is Phase 15+.
- **No Missions, Agents, or Tools.** CLAUDE.md §8–§11 describe them; V2 has not built them.
  What exists is the read pipeline they will be composed from.
- **No persistence for the audit trail.** `AuditSink` is a port with no writing
  implementation (see §3.1 of [platform-hardening](platform-hardening.md)).
- **No cost model.** Nothing prices a call, so `AuditRecord.estimated_cost` is always `None`.
- **No provider routing/fallback.** Adapters exist; a policy for choosing between them does
  not.
