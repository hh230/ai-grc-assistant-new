"""GenerationEngine hardening: retry semantics, error boundary, metrics, pass-through."""

from __future__ import annotations

import pytest

from generation_engine import GenerationEngine, RetryPolicy
from pipeline_contracts import (
    AuthenticationError,
    GenerationError,
    GenerationProvider,
    InvalidRequest,
    ProviderUnavailable,
    RateLimitError,
)
from pipeline_contracts import TimeoutError as GenerationTimeoutError

from tests.conftest import ANSWER, ScriptedProvider, make_request


def _engine(provider, **kwargs) -> tuple[GenerationEngine, list[float]]:
    sleeps: list[float] = []
    engine = GenerationEngine(provider, sleep=sleeps.append, **kwargs)
    return engine, sleeps


def test_engine_satisfies_the_generation_provider_port():
    engine, _ = _engine(ScriptedProvider(ANSWER))
    assert isinstance(engine, GenerationProvider)
    assert engine.name == "scripted"


def test_success_passes_the_request_through_unmodified():
    provider = ScriptedProvider(ANSWER)
    engine, sleeps = _engine(provider)
    request = make_request(temperature=0.1)

    answer = engine.generate(request)

    assert answer is ANSWER                      # the answer is not rewritten
    assert provider.requests == [request]
    assert provider.requests[0] is request       # the exact object, untouched
    assert sleeps == []                          # no retries → no backoff


@pytest.mark.parametrize("transient", [
    RateLimitError("throttled"), GenerationTimeoutError("slow"), ProviderUnavailable("down"),
])
def test_transient_errors_are_retried_with_backoff(transient):
    provider = ScriptedProvider(transient, ANSWER)
    engine, sleeps = _engine(provider, retry_policy=RetryPolicy(max_attempts=3, backoff_base_seconds=0.5))

    answer = engine.generate(make_request())

    assert answer is ANSWER
    assert len(provider.requests) == 2
    assert sleeps == [0.5]  # one backoff before the second attempt
    m = engine.last_metrics
    assert m.attempts == 2 and m.retries == 1 and m.succeeded
    assert m.retried_errors == [type(transient).__name__]


def test_backoff_grows_exponentially():
    provider = ScriptedProvider(RateLimitError("a"), RateLimitError("b"), ANSWER)
    engine, sleeps = _engine(provider, retry_policy=RetryPolicy(max_attempts=3, backoff_base_seconds=0.5))
    engine.generate(make_request())
    assert sleeps == [0.5, 1.0]


@pytest.mark.parametrize("fatal", [AuthenticationError("bad key"), InvalidRequest("too large")])
def test_non_retryable_errors_are_raised_immediately(fatal):
    provider = ScriptedProvider(fatal, ANSWER)
    engine, sleeps = _engine(provider)

    with pytest.raises(type(fatal)):
        engine.generate(make_request())

    assert len(provider.requests) == 1  # exactly one attempt
    assert sleeps == []
    assert engine.last_metrics.attempts == 1 and not engine.last_metrics.succeeded


def test_retries_exhausted_raises_the_last_domain_error():
    provider = ScriptedProvider(*[ProviderUnavailable("down")] * 3)
    engine, sleeps = _engine(provider, retry_policy=RetryPolicy(max_attempts=3))

    with pytest.raises(ProviderUnavailable):
        engine.generate(make_request())

    assert len(provider.requests) == 3
    assert engine.last_metrics.attempts == 3 and engine.last_metrics.retries == 2


def test_untranslated_sdk_exception_is_wrapped_never_raw():
    class WeirdSDKError(RuntimeError):
        pass

    provider = ScriptedProvider(WeirdSDKError("boom"))
    engine, _ = _engine(provider)

    with pytest.raises(GenerationError) as excinfo:
        engine.generate(make_request())

    assert not isinstance(excinfo.value, RuntimeError) or isinstance(excinfo.value, GenerationError)
    assert "WeirdSDKError" in str(excinfo.value)
    assert excinfo.value.provider == "scripted"
    assert not excinfo.value.retryable  # unknown failures are never retried


def test_metrics_sink_receives_the_run():
    received = []
    provider = ScriptedProvider(RateLimitError("x"), ANSWER)
    engine = GenerationEngine(provider, sleep=lambda _s: None, metrics_sink=received.append)

    engine.generate(make_request())

    assert len(received) == 1
    m = received[0]
    assert m.provider == "scripted" and m.model == "fake-1"
    assert m.attempts == 2 and m.retries == 1 and m.succeeded
    assert len(m.attempt_latencies_ms) == 2
    assert m.latency_ms >= 0


def test_metrics_recorded_on_failure_too():
    provider = ScriptedProvider(AuthenticationError("no"))
    engine, _ = _engine(provider)
    with pytest.raises(AuthenticationError):
        engine.generate(make_request())
    assert engine.last_metrics is not None
    assert engine.last_metrics.succeeded is False
