"""Pipeline tracing — a pure, provider-neutral abstraction for timing the AI pipeline.

The whole model is three plain objects and one context manager:

    Tracer            owns a Trace and hands out Spans
      └─ Span         times one stage (a `with` block) and records it on close
           └─ StageTiming   the immutable result: name, duration, timestamps, metadata
    Trace             the trace id + the ordered StageTimings + the total duration

It is *only the abstraction*: no logging framework, no exporter, no external
observability service, no OpenTelemetry. A `Trace` is a plain, serializable record; a later
phase may forward it wherever it likes. The clock is injectable so tests are deterministic
and the module never reaches for wall-time implicitly. Depends on nothing.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from types import TracebackType
from typing import Callable


@dataclass(frozen=True)
class StageTiming:
    """One stage's timing record. `duration_ms` is monotonic (from `perf_counter`) so it is
    immune to wall-clock adjustments; `started_at` / `ended_at` are epoch-second wall
    timestamps for human-readable ordering. `error` names the exception type when the stage
    raised — a failed stage is still timed and recorded, never dropped."""

    name: str
    duration_ms: float
    started_at: float
    ended_at: float
    metadata: dict[str, object] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "duration_ms": round(self.duration_ms, 3),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "metadata": dict(self.metadata),
            "error": self.error,
        }


class Span:
    """A single stage's live timer, used as a context manager:

        with tracer.stage("retrieval", top_k=8) as span:
            ...
            span.annotate(candidates=42)

    On exit it records a `StageTiming` onto the tracer — whether the block returned or
    raised. `annotate` accumulates structured metadata during the stage. A Span records
    exactly once; re-entering or leaking it is a no-op after the first close."""

    def __init__(self, tracer: Tracer, name: str, metadata: dict[str, object]) -> None:
        self._tracer = tracer
        self._name = name
        self._metadata: dict[str, object] = dict(metadata)
        self._start_perf = 0.0
        self._start_wall = 0.0
        self._closed = False

    def annotate(self, **metadata: object) -> Span:
        """Attach structured metadata to this stage; chainable. Ignored after close."""
        if not self._closed:
            self._metadata.update(metadata)
        return self

    def __enter__(self) -> Span:
        self._start_perf = self._tracer.clock()
        self._start_wall = self._tracer.wall_clock()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        self._close(error=exc_type.__name__ if exc_type is not None else None)
        return False  # never suppress the exception — tracing must be transparent

    def _close(self, *, error: str | None) -> None:
        if self._closed:
            return
        self._closed = True
        end_perf = self._tracer.clock()
        timing = StageTiming(
            name=self._name,
            duration_ms=(end_perf - self._start_perf) * 1000.0,
            started_at=self._start_wall,
            ended_at=self._tracer.wall_clock(),
            metadata=self._metadata,
            error=error,
        )
        self._tracer.record(timing)


@dataclass
class Trace:
    """The accumulated record of one pipeline run: the trace id plus the ordered stage
    timings. `total_ms` is the sum of the recorded stages (not wall-clock span), so it stays
    meaningful even if stages are timed non-contiguously."""

    trace_id: str
    stages: list[StageTiming] = field(default_factory=list)

    @property
    def total_ms(self) -> float:
        return sum(s.duration_ms for s in self.stages)

    def stage(self, name: str) -> StageTiming | None:
        return next((s for s in self.stages if s.name == name), None)

    def timings_ms(self) -> dict[str, float]:
        """Stage name → duration, the flat shape most consumers want."""
        return {s.name: round(s.duration_ms, 3) for s in self.stages}

    def to_dict(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "total_ms": round(self.total_ms, 3),
            "stages": [s.to_dict() for s in self.stages],
        }


class Tracer:
    """Owns a `Trace` and hands out `Span`s. Construct one per pipeline run. `clock` (a
    monotonic source, default `perf_counter`) and `wall_clock` (epoch seconds, default
    `time.time`) are injectable so tests are fully deterministic. A generated trace id is
    used when none is supplied."""

    def __init__(
        self,
        *,
        trace_id: str | None = None,
        clock: Callable[[], float] = time.perf_counter,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self.clock = clock
        self.wall_clock = wall_clock
        self._trace = Trace(trace_id=trace_id or uuid.uuid4().hex)

    @property
    def trace(self) -> Trace:
        return self._trace

    @property
    def trace_id(self) -> str:
        return self._trace.trace_id

    def stage(self, name: str, **metadata: object) -> Span:
        """Open a timing span for `name`. Use it as a `with` block."""
        return Span(self, name, metadata)

    def record(self, timing: StageTiming) -> None:
        """Append a completed timing. Called by `Span` on close; public so a caller can add
        externally measured stages (e.g. a sub-engine's own timing) to the same trace."""
        self._trace.stages.append(timing)


def new_trace_id() -> str:
    """The one place a trace id is minted, so every layer agrees on the format."""
    return uuid.uuid4().hex
