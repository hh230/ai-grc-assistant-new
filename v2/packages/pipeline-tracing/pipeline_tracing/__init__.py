"""Rasheed V2 Pipeline Tracing (Phase 13).

A pure, provider-neutral tracing abstraction: a trace id, per-stage timings, total
execution duration, and structured metadata. Only the abstraction — no logging framework,
no exporter, no OpenTelemetry. Depends on nothing.
"""

from pipeline_tracing.tracing import (
    Span,
    StageTiming,
    Trace,
    Tracer,
    new_trace_id,
)

__all__ = [
    "Tracer",
    "Trace",
    "Span",
    "StageTiming",
    "new_trace_id",
]
