# Rasheed V2 — Platform Hardening Architecture

- Status: **Implemented (Phase 13).** Packages: `v2/packages/answer-validation/`,
  `v2/packages/pipeline-tracing/`, `v2/packages/event-bus/`, and new adapters in
  `v2/packages/generation-engine/`.
- Date: 2026-07-14
- Companions: [Prompt Orchestrator](prompt-orchestrator.md) (supplies the `LLMRequest` +
  `ResponseContract`), [Context Builder](context-builder.md) (supplies the `ContextPackage`),
  [ADR 0038](../../../docs/adr/0038-v2-pipeline-contracts-and-ai-orchestrator.md),
  [ADR 0039](../../../docs/adr/0039-v2-platform-hardening.md).
- Scope boundary: **v2/ only.** This phase hardens the platform *around* the existing
  pipeline. It adds no AI capability and changes no existing engine's behaviour — no
  redesign, no business-logic/workflow/retrieval/prompting change.

---

## 0. Why a hardening phase

The core read pipeline (Phase 12) turns a `UserRequest` into an `Answer` through composed
hexagonal engines. Production operation needs scaffolding *around* that pipeline: the answer
must be **validated**, a run must be **observable** and **auditable**, and generation must not
be locked to one vendor. Each of those is added here as an independent, opt-in unit — the
pipeline itself is untouched.

```
                 ┌──────────────── AI Orchestrator (composition root) ───────────────┐
  UserRequest ─→ │ Decision → Retrieval → Context → Prompt → Generation → Validation │ ─→ PipelineResult
                 └────────┬──────────────┬─────────────┬───────────────┬─────────────┘
                          │ Tracer span each stage      │ publish domain events        │
                          ▼                              ▼                              ▼
                   pipeline-tracing               event-bus (in-process)        answer-validation
                     (Trace)              (RetrievalCompleted, PromptBuilt,      (ValidatedAnswer)
                                           GenerationCompleted, AnswerValidated,
                                           PipelineCompleted ← terminal)
                                                        │
                                                        ▼
                                          AuditTrailBuilder → AuditRecord → AuditSink
```

All three side-channels are **opt-in**. With none wired, the orchestrator runs exactly as in
Phase 12.

> **Phase 14.5 update.** `PipelineCompleted` is the terminal event, published on *every* path
> a run can end on, and it — not `AnswerValidated` — is what closes the audit trail. See
> [§3.1](#31-the-audit-trail-completed-phase-145) for what changed and why.

---

## 1. Answer Validation Engine — `answer-validation`

Contract: `Answer + ContextPackage + ResponseContract → ValidatedAnswer`. It **only
validates** — never generates, retrieves, extracts citations from the model, or mutates the
answer. The `ValidatedAnswer` wraps the *same* `Answer` object with a verdict:

```
ValidatedAnswer
  ├─ answer                 the original Answer (identity preserved — never copied/edited)
  ├─ status                 passed | warnings | failed
  ├─ issues[]               ValidationIssue(code, severity, message, detail)
  └─ confidence_adjustment  a SUGGESTED downward nudge (≤ 0) — applied by nobody here
```

Deterministic, structural checks (the finite `ValidationCode` set):

| Code | Severity | Fires when |
|---|---|---|
| `empty_answer` | error | the answer text is blank |
| `missing_citations` | error | citations required, evidence existed, none cited |
| `unknown_citation` | error | cites `[S<n>]` absent from the `ContextPackage` (fabrication) |
| `malformed_citation` | warning | a marker that isn't the `[S<n>]` form |
| `missing_confidence` | warning | a confidence level is required but none stated |
| `unsupported_confidence` | warning | the stated confidence isn't high/medium/low |
| `missing_section` | warning | a required section heading is absent |

Citations are matched to the marker style the Prompt Orchestrator renders (`[S1]`, `[S2]`, …
indexing the ordered `ContextPackage` blocks), so "cites a source that isn't in the context"
is decidable exactly. **Semantic prohibitions** (`forbidden_outputs` such as "legal advice")
are guidance to the model, not something a string match can adjudicate — they are **not**
flagged here; that belongs to a future reviewer phase (a non-goal). Errors fail the answer;
warnings never do. Depends only on `pipeline-contracts`.

---

## 2. Pipeline Tracing — `pipeline-tracing`

A pure abstraction, dependency-free. Only a trace id, per-stage timings, total duration, and
structured metadata — no logging framework, no exporter, no OpenTelemetry.

```
Tracer(trace_id, clock, wall_clock)      # clocks injectable → deterministic tests
  └─ stage(name, **meta) → Span          # a context manager
        └─ records StageTiming(name, duration_ms, started_at, ended_at, metadata, error)
Trace                                     # trace_id + ordered StageTiming[] + total_ms
```

A `Span` records its `StageTiming` on exit **whether the stage returns or raises** (a failed
stage is still timed, with `error` set), then re-raises transparently. `duration_ms` comes
from a monotonic clock; `started_at`/`ended_at` are wall timestamps.

---

## 3. Event Bus & Audit Trail — `event-bus`

Provider-agnostic, **synchronous, in-process** — no Kafka/RabbitMQ/Redis, dependency-free.

- **Domain events** (immutable, past-tense facts, carrying summary fields only — never whole
  `ContextPackage`s or SDK objects): `RetrievalCompleted`, `PromptBuilt`, `GenerationCompleted`,
  `AnswerValidated`, and the terminal `PipelineCompleted`. Each has a stable `name` and a
  `trace_id`.
- **`EventBus` port** + **`InProcessEventBus`** dispatcher: subscribe by event type or to
  `ALL_EVENTS`; `publish` calls each matching handler inline, in registration order. Handler
  isolation is opt-in via an injected `error_handler` (loud by default).
- **Audit Trail**: `AuditRecord` + the `AuditSink` **interface** — **model and interface only,
  no persistence** (an `InMemoryAuditSink` exists purely for tests/demos). `AuditTrailBuilder`
  subscribes to the bus and assembles one record per trace from the same event stream, so the
  audit trail is *derived*, not a parallel bookkeeping path.

### 3.1 The audit trail, completed (Phase 14.5)

Phase 13 shipped the audit model with two gaps, both closed here. The Event Bus itself is
unchanged: same port, same in-process dispatcher, same derived-from-events design.

**Gap 1 — the trail only closed if validation ran.** `AuditTrailBuilder` finalized on
`AnswerValidated`, which is published only when an `AnswerValidator` is wired. Since
validation is opt-in, the default pipeline produced *no audit record at all* unless a caller
remembered to call `finalize` by hand. Audit that depends on an optional stage is not audit.

The fix is a terminal event rather than a terminal *stage*: the composition root publishes
**`PipelineCompleted`** from `_finish` — the single function every terminal path routes
through — so a record is produced whether the run answered, was refused for an invalid
prompt, or paused at a human gate. Optional stages now only *enrich* the record; none of them
closes it.

```
  retrieval.completed → prompt.built → generation.completed → answer.validated → pipeline.completed
     (optional)          (always)         (if generated)         (if wired)         (ALWAYS — terminal)
       │                    │                  │                     │                    │
       └─ source_ids        └─ intent,         └─ usage,             └─ status,           └─ finalize
                               prompt_versions    estimated_cost        passed              → AuditSink
```

A run that never validates records `validation_status = "not_configured"` — an explicit
outcome, because "nobody checked" and "the check passed" are different audit facts and an
empty field would force an auditor to guess which one it meant.

**Gap 2 — the record could not reproduce a run.** CLAUDE.md §19 requires that an auditor can
reconstruct *how* an output was produced. The Phase 13 record named the workflow, provider,
and model — not what grounded the answer, which prompt produced it, or what it cost. The
record now carries:

| Field | Source event | Answers |
|---|---|---|
| `trace_id`, `started_at`, `completed_at`, `duration_s` | all | when, and which run |
| `workflow`, `intent` | `PromptBuilt` | what was asked for |
| `provider`, `model` | `GenerationCompleted` | which model answered |
| `prompt_versions` | `PromptBuilt` | which versioned prompts produced it |
| `source_ids` | `RetrievalCompleted` | which sources grounded it |
| `usage`, `estimated_cost` | `GenerationCompleted` | what it consumed |
| `status` | `PipelineCompleted` | how the run ended |
| `warnings` | all | what went wrong along the way |
| `validation_status`, `validation_passed` | `AnswerValidated` | whether the answer was checked, and the verdict |

`estimated_cost` is `None` on every run today: the platform has no cost model, so nothing can
price a call. The field exists so the record's shape does not have to change when one lands —
it is left absent rather than filled with a fabricated number. Pricing is Phase 15+.

**Still not persistence.** `AuditSink` remains the port, and no implementation of it writes
anywhere. A durable, append-only, tenant-scoped sink needs the tenant model
([ADR 0040](../../../docs/adr/0040-v2-tenancy-model.md)) — an `AuditRecord` with no
`tenant_id` cannot be stored in a tenant-scoped log.

---

## 4. Provider expansion — `generation-engine`

Adapters **only** for Claude, Gemini, and Ollama alongside OpenAI. Each:

- implements the existing `GenerationProvider` port (`name` + `generate`);
- maps the request's provider-neutral `messages()` fold + `params` onto its SDK, and the SDK
  response back into the shared `Answer` (Claude lifts the system prompt to the top-level
  `system` arg; Gemini to `config.system_instruction`; Ollama passes messages straight);
- translates SDK exceptions into the shared domain errors (`_errors.translate_sdk_error`, by
  HTTP status then class name) so the engine's **existing retry** logic works unchanged;
- hides its SDK behind an optional extra: `generation-engine[claude|gemini|ollama]`.

**No routing, no fallback, no selection, no comparison** — the engine still executes exactly
the one provider wired into it. The OpenAI adapter and the engine core are unchanged.

---

## 5. Composition-root wiring (opt-in)

`AIOrchestrator` gains three optional collaborators — `answer_validator`, `event_bus`,
`enable_tracing` — all defaulting to off:

- **tracing**: when enabled, each stage is wrapped in a `Tracer` span and the resulting
  `Trace` is attached to `PipelineResult.trace`;
- **events**: `RetrievalCompleted` / `PromptBuilt` / `GenerationCompleted` / `AnswerValidated`
  are published at their stage boundaries; publication is **fail-safe** (a broken subscriber
  degrades to a warning, never breaking the run);
- **validation**: a post-generation `VALIDATION` stage runs the validator and attaches the
  `ValidatedAnswer` to `PipelineResult.validated`. It **never mutates** the answer and **never
  fails** the run — a poor answer is reported (warnings/errors surfaced), not suppressed.

With none configured, `PipelineResult.validated` and `.trace` are `None` and the run is
byte-for-byte the Phase 12 behaviour.

---

## 6. What this phase is NOT

No agent framework, tool calling, JSON mode, vision, audio, streaming, reflection, reviewer,
memory, multi-provider routing, provider fallback, pricing engine, human-approval workflow,
persistent audit storage, OpenTelemetry, Kafka, RabbitMQ, or Redis. Those are later phases.

---

## 7. Tests

Package suites, all green (deterministic; no network, no live SDK):

| Package | Tests |
|---|---|
| answer-validation | 23 |
| pipeline-tracing | 14 |
| event-bus | 27 |
| generation-engine (26 prior + 29 new adapter tests) | 55 |
| ai-orchestrator (19 prior + 11 hardening tests) | 30 |

The prior engines (decision, retrieval, context, prompt) are unchanged and their suites
(63 / 29 / 47 / 51) remain green.
