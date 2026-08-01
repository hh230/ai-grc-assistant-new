# ADR 0039: Rasheed V2 — platform hardening (answer validation, tracing, event bus & audit trail, provider expansion)

- Status: Accepted — implemented (Phase 13)
- Date: 2026-07-14
- Deciders: Product Owner (via approved implementation task), Architecture
- Related: CLAUDE.md §3, §5, §6, §7, §9, §16, §19; ADR 0038 (pipeline-contracts +
  ai-orchestrator); architecture doc
  [platform-hardening](../../v2/docs/architecture/platform-hardening.md)

## Context

Phase 12 completed the core read pipeline as a set of hexagonal engines composed by the
`ai-orchestrator`: `UserRequest → DecisionEngine → RetrievalEngine → ContextBuilder →
PromptOrchestrator → GenerationEngine → Answer`. What was still missing was the
*operational* scaffolding a regulated, multi-tenant platform needs around that pipeline:

1. **Nothing validated the generated answer.** The `ResponseContract` was rendered into the
   prompt and kept structured (ADR 0038) precisely so a later stage could check the answer
   against it, but that stage did not exist. An ungrounded or fabricated-citation answer
   could reach a caller unflagged — unacceptable under CLAUDE.md §12/§19.
2. **There was no first-class tracing or event model.** The orchestrator recorded stage
   timings and emitted string-named lifecycle events through an optional hook, but there
   was no reusable trace object and no typed domain events other layers could observe or
   audit against.
3. **Generation had a single adapter (OpenAI).** The `GenerationProvider` port was designed
   for many providers, but only one existed, coupling any deployment to one vendor's
   availability.

This phase hardens the platform around the existing pipeline. It adds **no** AI capability
and changes **no** existing engine's behaviour: no redesign, no business-logic change, no
workflow change, no retrieval or prompting change.

## Decision

We add four capabilities, each as a **new, independently testable unit**, and wire them into
the composition root **additively and opt-in** so a run with none of them configured behaves
exactly as before.

**1. Answer Validation Engine** — new package `v2/packages/answer-validation/`. It validates
a generated `Answer` against the existing `ContextPackage`, its citations, and the
`ResponseContract`, returning a `ValidatedAnswer` (the *unchanged* answer + status + errors +
warnings + a *suggested* confidence adjustment). It only validates — it never generates,
retrieves, extracts citations from the model, or mutates the answer. Checks are deterministic
and structural: empty answers, missing citations, malformed `[S<n>]` markers, citations
absent from the `ContextPackage` (fabrication), unsupported/absent confidence values, and
missing required sections. Semantic prohibitions (`forbidden_outputs`) are **not** adjudicated
here — that is a future reviewer phase (an explicit non-goal). Depends only on
`pipeline-contracts`.

**2. Pipeline Tracing** — new package `v2/packages/pipeline-tracing/`. A pure, provider-neutral
abstraction: a `Tracer` hands out `Span`s (context managers) that record `StageTiming`s onto a
`Trace` (trace id + ordered stage timings + total duration + structured metadata). Only the
abstraction — no logging framework, no exporter, no OpenTelemetry. Depends on nothing.

**3. Event Bus & Audit Trail** — new package `v2/packages/event-bus/`. A provider-agnostic,
**synchronous, in-process** event architecture: immutable domain events
(`RetrievalCompleted`, `PromptBuilt`, `GenerationCompleted`, `AnswerValidated`), an `EventBus`
port, and an `InProcessEventBus` local dispatcher — no Kafka, RabbitMQ, or Redis. Plus the
Audit Trail domain model (`AuditRecord`: trace id, timestamps, workflow, provider, model,
warnings, validation result) and its `AuditSink` interface — **model and interfaces only, no
persistence**. An `AuditTrailBuilder` assembles records from the same event stream. Depends on
nothing.

**4. Provider expansion** — the Generation Engine gains **adapters only** for Claude, Gemini,
and Ollama alongside OpenAI. Each implements the existing `GenerationProvider` port, translates
its SDK's errors into the shared domain errors (so the engine's existing retry logic works
unchanged), and hides its SDK behind an optional extra (`generation-engine[claude|gemini|ollama]`),
exactly as OpenAI already did. **No routing, no fallback, no provider selection, no
comparison** — those are later phases.

**Composition-root wiring.** `AIOrchestrator` gains three optional collaborators —
`answer_validator`, `event_bus`, and `enable_tracing` — all defaulting to off. When set, it
publishes the four domain events at their stage boundaries, records a `Trace`, and runs a
post-generation validation stage whose `ValidatedAnswer` is attached to the `PipelineResult`.
Validation never mutates the answer and never fails the run (a poor answer is reported, not
suppressed); event publication is fail-safe (a broken subscriber degrades to a warning). This
is the composition root's stated job (ADR 0038: "the future event / human-approval hooks",
"tracing"), not a redesign of any engine. The five pipeline engines
(decision/retrieval/context/prompt/generation) are untouched.

We reuse the existing contracts throughout — `LLMRequest`, `Answer`, `ContextPackage`,
`ResponseContract`, `GenerationProvider` — and introduce no parallel models.

Resulting dependency graph (arrows = "depends on"; dev-only test deps excluded):

```
pipeline-contracts        (pure; depends on nothing)
pipeline-tracing          (pure; depends on nothing)
event-bus                 (pure; depends on nothing)

answer-validation ─→ pipeline-contracts
generation-engine ─→ pipeline-contracts        (+ optional SDK extras: openai/claude/gemini/ollama)

ai-orchestrator ─→ decision-engine ─┐
      │ ─→ retrieval-engine ─────────┤
      │ ─→ context-builder ──────────┤─→ pipeline-contracts
      │ ─→ prompt-orchestrator ──────┤
      │ ─→ generation-engine ────────┘
      │ ─→ answer-validation
      │ ─→ pipeline-tracing
      └ ─→ event-bus
```

## Consequences

**Positive**
- Generated answers are checked against their grounding and contract before a caller sees
  them; fabricated citations and ungrounded claims are caught deterministically (CLAUDE.md
  §12, §19).
- A run is observable (structured `Trace`) and auditable (typed events + `AuditRecord`)
  without committing to any logging or messaging technology.
- Generation is no longer coupled to one vendor; adding a provider is an adapter + an extra,
  with zero change to the engine, the orchestrator, or any business code.
- Every new unit is pure or contract-only, independently tested, and added at the edges —
  the platform grew without the core changing (CLAUDE.md §17).

**Negative / costs**
- `PipelineResult` gains two nullable fields (`validated`, `trace`); its `to_dict` now emits
  two extra `null` keys on a bare run. Additive and backward-compatible, but a schema delta.
- The new provider adapters cannot be exercised against live SDKs in CI; they are verified
  via injected fakes for request/response mapping and SDK→domain error translation, the same
  bar the OpenAI adapter meets.
- Validation is intentionally structural. It does not judge semantic quality or catch
  prohibited *content*; that awaits a reviewer phase and must not be assumed here.

## Alternatives considered

- **Put `ValidatedAnswer`, events, `AuditRecord`, and `Trace` into `pipeline-contracts`.**
  Rejected: these are outputs/abstractions owned by specific new units, not shapes that flow
  *between* the existing engines. Keeping them in their own packages preserves the rule that
  `pipeline-contracts` holds only cross-engine contracts, and keeps tracing/event-bus fully
  dependency-free.
- **Make tracing and events always-on inside the orchestrator.** Rejected: it would change
  the default run's behaviour and serialization. Opt-in keeps the zero-change guarantee.
- **Add provider routing/fallback now.** Rejected: out of scope and premature — routing needs
  a policy (cost/latency/capability) that belongs to a later phase. This phase ships adapters
  only.
- **Persist the audit trail in this phase.** Rejected: the task scopes the audit trail to the
  domain model and interface; a storage adapter (DB / append-only log) is a later phase behind
  the `AuditSink` port.

## Amendment — Phase 14.5 (2026-07-16): the audit trail completed

The Phase 13 decision above stands: the Event Bus keeps its port, its synchronous in-process
dispatcher, and its derived-from-events audit design. Two gaps in the *audit trail* built on
it are closed here. Nothing about the bus is redesigned, and no persistence is added — the
`AuditSink` port still has no implementation that writes anywhere.

**1. Finalization no longer depends on an optional stage.** `AuditTrailBuilder` finalized on
`AnswerValidated`. Validation is opt-in (that was the whole point of the additive wiring), so
a pipeline with no `AnswerValidator` published no terminal event and produced **no audit
record at all** unless a caller invoked `finalize` by hand. An audit trail that only exists
when an optional collaborator is configured does not satisfy CLAUDE.md §19.

We add **`PipelineCompleted`** — a fifth domain event, terminal, published by the composition
root from `_finish`, the one function every terminal path routes through (answered, invalid
prompt, awaiting approval). The builder finalizes on it. `AnswerValidated` now only records
the verdict; it no longer closes the run. A run with no validator records
`validation_status = "not_configured"`, an explicit outcome rather than a blank field an
auditor would have to interpret.

*This is a behavioural change to the audit builder, and the only one in the phase:* a caller
that fed the four Phase 13 events and relied on `AnswerValidated` to emit a record must now
publish `PipelineCompleted` or call `finalize` (which remains public and unchanged). The
`ai-orchestrator` publishes the terminal event on every path, so any pipeline composed
through it gains this for free. No engine's behaviour and no `PipelineResult` changed.

**2. The record can now reproduce a run.** Phase 13's `AuditRecord` named the workflow,
provider, model, timestamps, warnings, and validation result — but not what grounded the
answer, which prompt version produced it, or what it consumed, which CLAUDE.md §19 requires.
The record gains `intent`, `prompt_versions`, `source_ids` (the retrieved chunk ids, in rank
order), `usage`, `estimated_cost`, and the terminal `status`. The events carry these as
summary fields only — ids and counts, never chunk text or SDK objects — so the bus stays the
thin notification layer this ADR made it.

`estimated_cost` is `None` on every run: no cost model exists in the platform, so nothing can
price a call. The field is declared so the record's shape survives one arriving; it is never
populated with an estimate the platform cannot substantiate.

**What remains open.** The record still carries no `tenant_id`, which is why the `AuditSink`
port still has no persistent implementation: a durable audit log must be tenant-scoped and
append-only, and a record cannot be filed under a tenant it does not name.
[ADR 0040](./0040-v2-tenancy-model.md) fixes that contract; the build is Phase 15+.
