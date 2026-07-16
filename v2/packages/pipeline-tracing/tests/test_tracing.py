"""Tracer behaviour under a deterministic injected clock — no real time, no flakiness."""

from __future__ import annotations

import pytest

from pipeline_tracing import StageTiming, Trace, Tracer, new_trace_id


class FakeClock:
    """A monotonic clock that advances by a fixed step on every read, so durations are
    exact and predictable."""

    def __init__(self, *, step: float = 0.5, start: float = 100.0) -> None:
        self._t = start
        self._step = step

    def __call__(self) -> float:
        now = self._t
        self._t += self._step
        return now


def make_tracer(*, step: float = 0.5, trace_id: str = "trace-1") -> Tracer:
    # perf clock advances by `step`; wall clock is fixed so timestamps are stable.
    return Tracer(trace_id=trace_id, clock=FakeClock(step=step), wall_clock=lambda: 1_700.0)


def test_trace_id_is_used_and_exposed():
    tracer = make_tracer(trace_id="abc")
    assert tracer.trace_id == "abc"
    assert tracer.trace.trace_id == "abc"


def test_generated_trace_id_when_absent():
    tracer = Tracer()
    assert tracer.trace_id
    assert len(tracer.trace_id) == 32  # uuid4 hex


def test_stage_records_duration_from_the_clock():
    tracer = make_tracer(step=0.5)  # enter reads t, exit reads t+0.5 → 500ms
    with tracer.stage("retrieval"):
        pass
    timing = tracer.trace.stage("retrieval")
    assert timing is not None
    assert timing.duration_ms == pytest.approx(500.0)
    assert timing.ok


def test_annotate_accumulates_metadata():
    tracer = make_tracer()
    with tracer.stage("decision", intent="lookup") as span:
        span.annotate(candidates=42).annotate(reranked=True)
    timing = tracer.trace.stage("decision")
    assert timing.metadata == {"intent": "lookup", "candidates": 42, "reranked": True}


def test_stage_is_recorded_even_when_it_raises_and_the_error_propagates():
    tracer = make_tracer()
    with pytest.raises(ValueError):
        with tracer.stage("generation") as span:
            span.annotate(provider="openai")
            raise ValueError("boom")
    timing = tracer.trace.stage("generation")
    assert timing is not None
    assert timing.error == "ValueError"
    assert not timing.ok
    assert timing.metadata == {"provider": "openai"}


def test_total_ms_sums_stage_durations_and_preserves_order():
    tracer = make_tracer(step=0.5)  # every stage measures 500ms
    for name in ("decision", "retrieval", "generation"):
        with tracer.stage(name):
            pass
    trace = tracer.trace
    assert [s.name for s in trace.stages] == ["decision", "retrieval", "generation"]
    assert trace.total_ms == pytest.approx(1500.0)
    assert trace.timings_ms() == {
        "decision": pytest.approx(500.0),
        "retrieval": pytest.approx(500.0),
        "generation": pytest.approx(500.0),
    }


def test_record_accepts_externally_measured_stages():
    tracer = make_tracer()
    tracer.record(StageTiming(name="sub-engine", duration_ms=12.0, started_at=1.0, ended_at=1.012))
    assert tracer.trace.stage("sub-engine").duration_ms == 12.0


def test_annotate_after_close_is_ignored():
    tracer = make_tracer()
    with tracer.stage("prompt") as span:
        pass
    span.annotate(late=True)  # after close — must not mutate the recorded timing
    assert tracer.trace.stage("prompt").metadata == {}


def test_trace_to_dict_is_plain_and_serializable():
    tracer = make_tracer(step=0.25)
    with tracer.stage("decision", intent="lookup"):
        pass
    data = tracer.trace.to_dict()
    assert data["trace_id"] == "trace-1"
    assert data["total_ms"] == pytest.approx(250.0)
    assert data["stages"][0]["name"] == "decision"
    assert data["stages"][0]["metadata"] == {"intent": "lookup"}
    assert data["stages"][0]["error"] is None
    import json
    json.dumps(data)  # must be JSON-serializable end to end


def test_new_trace_id_is_unique_hex():
    assert new_trace_id() != new_trace_id()


def test_trace_can_be_built_empty():
    trace = Trace(trace_id="empty")
    assert trace.total_ms == 0.0
    assert trace.timings_ms() == {}
    assert trace.stage("missing") is None
