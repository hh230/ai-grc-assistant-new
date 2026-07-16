# pipeline-tracing

A pure, provider-neutral abstraction for timing the AI pipeline. Depends on **nothing**.

```
Tracer            owns a Trace and hands out Spans
  └─ Span         times one stage (a `with` block) and records it on close
       └─ StageTiming   the immutable result: name, duration, timestamps, metadata, error
Trace             the trace id + the ordered StageTimings + the total duration
```

## Only the abstraction

No logging framework, no exporter, no external observability service, **no OpenTelemetry**. A
`Trace` is a plain, serializable record; forwarding it somewhere is a later phase's decision,
and keeping that decision out of this package is what lets it stay dependency-free.

## Usage

```python
tracer = Tracer(trace_id="abc123")
with tracer.stage("retrieval", top_k=8):
    ...
trace = tracer.trace          # serializable via trace.to_dict()
```

Two details that matter:

- **The clock is injectable**, so tests are deterministic and the module never reaches for
  wall-time implicitly. `duration_ms` comes from `perf_counter` (monotonic — immune to
  wall-clock adjustments); `started_at` / `ended_at` are epoch seconds for human-readable
  ordering.
- **A failed stage is still timed and recorded**, with `error` naming the exception type. A
  stage that blew up is exactly the one you want a timing for; dropping it would hide the
  most interesting span in the trace.

## Wiring

Opt-in. With `enable_tracing=False` (the default) no `Tracer` is constructed and
`PipelineResult.trace` is `None` — the run behaves exactly as it did before this package
existed.

```python
AIOrchestrator(..., enable_tracing=True)
```

The orchestrator's own `metrics.timings_ms` bookkeeping is independent and unchanged; the
tracer times each stage separately and additionally records failures.

## Related

- [ADR 0039](../../../docs/adr/0039-v2-platform-hardening.md) — this package's decision
- [Platform hardening architecture](../../docs/architecture/platform-hardening.md) §2
