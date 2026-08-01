# event-bus

The Rasheed V2 domain-event architecture and the Audit Trail derived from it.

Provider-agnostic, **synchronous, in-process** — no Kafka, no RabbitMQ, no Redis, and no
dependencies at all (not even on `pipeline-contracts`, so the observability layer can never
become a reason for a contract to change).

## What's here

| Module | Contents |
|---|---|
| `event_bus.events` | The immutable, past-tense domain facts: `RetrievalCompleted`, `PromptBuilt`, `GenerationCompleted`, `AnswerValidated`, `PipelineCompleted`, over the `DomainEvent` base (`name` + `trace_id` + `occurred_at`) |
| `event_bus.bus` | The `EventBus` port, the `InProcessEventBus` dispatcher, and `RecordingEventBus` for tests |
| `event_bus.audit` | `AuditRecord`, the `AuditSink` port, `InMemoryAuditSink`, and `AuditTrailBuilder` |

## The events

```
retrieval.completed → prompt.built → generation.completed → answer.validated → pipeline.completed
   (optional)          (always)         (if generated)         (if wired)         (ALWAYS — terminal)
```

Events carry **summary fields only** — counts, ids, provider names — never a whole
`ContextPackage` or an SDK object. That is what keeps the bus a thin notification layer with
no dependency on the pipeline's contracts; the composition root maps rich artifacts down to
summaries when it publishes.

`PipelineCompleted` is the terminal event. The AI Orchestrator publishes it from `_finish`,
the one function every terminal path routes through, so it fires whether a run answered, was
refused for an invalid prompt, or paused at a human gate.

## The bus

`InProcessEventBus.publish` calls each matching handler inline, in registration order, and
returns when they are done. Subscribe by event type (`bus.subscribe(PromptBuilt, handler)`)
or to everything (`bus.subscribe_all(handler)` — what audit sinks and tracers do).

Handler isolation is **opt-in**: inject an `error_handler` and a handler that raises is routed
to it while dispatch continues; with none, the exception propagates (loud by default, per the
coding standards). The AI Orchestrator wraps publication so a broken bus degrades to a warning
and never breaks a run — events are observability, not the answer path.

## The audit trail

```python
sink = InMemoryAuditSink()
bus = InProcessEventBus()
bus.subscribe_all(AuditTrailBuilder(sink=sink).handle)
orchestrator = AIOrchestrator(..., event_bus=bus)
```

`AuditTrailBuilder` accumulates per `trace_id` and emits one finalized `AuditRecord` on
`PipelineCompleted`. The trail is **derived from the same event stream everything else
observes** — not a parallel bookkeeping path. Feeding events by hand instead? `finalize(trace_id)`
closes a run explicitly.

Every completed run produces a complete record (CLAUDE.md §19):

| Field | Answers |
|---|---|
| `trace_id`, `started_at`, `completed_at`, `duration_s` | when, and which run |
| `workflow`, `intent` | what was asked for |
| `provider`, `model` | which model answered |
| `prompt_versions` | which versioned prompts produced it |
| `source_ids` | which sources grounded it |
| `usage`, `estimated_cost` | what it consumed |
| `status` | how the run ended |
| `warnings` | what went wrong along the way |
| `validation_status`, `validation_passed` | whether the answer was checked, and the verdict |

Two things worth knowing:

- **`estimated_cost` is always `None` today.** There is no cost model in the platform, so
  nothing can price a call. The field exists so the record's shape survives one arriving —
  it is left absent rather than filled with a fabricated number.
- **`validation_status` is `"not_configured"` when no validator is wired**, never blank:
  "nobody checked" and "the check passed" are different audit facts.

## Not persistence

`AuditSink` is the **port**. Nothing in this package writes anywhere — `InMemoryAuditSink`
holds records in a list for tests and demos and is explicitly not durable storage. A real
sink must be append-only and tenant-scoped, which needs the tenant model first
([ADR 0040](../../../docs/adr/0040-v2-tenancy-model.md)): a record cannot be filed under a
tenant it does not name. Phase 15+.

## Related

- [ADR 0009](../../../docs/adr/0009-event-driven-architecture.md) — EDA where it earns its keep
- [ADR 0015](../../../docs/adr/0015-audit-and-traceability.md) — audit & traceability
- [ADR 0039](../../../docs/adr/0039-v2-platform-hardening.md) — this package's decision, plus
  the Phase 14.5 amendment that completed the trail
- [Platform hardening architecture](../../docs/architecture/platform-hardening.md) §3
