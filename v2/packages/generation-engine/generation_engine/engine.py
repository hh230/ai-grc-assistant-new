"""The Generation Engine — a hardened wrapper around the `GenerationProvider` port.

It adds exactly four things to a provider: **retry** (transient domain errors only, with
backoff), **execution timing**, **metrics** (attempt-level detail no other layer can see),
and an **error-translation guard** (anything that escapes an adapter untranslated is wrapped
in a domain `GenerationError`, so callers never see an SDK exception).

It deliberately does NOT: choose providers, choose models, route requests, modify prompts,
validate answers, or inject citations. It executes exactly the `LLMRequest` it receives —
the request object is passed to the adapter untouched.

The engine itself satisfies the `GenerationProvider` protocol (`name` + `generate`), so it
drops into any injection point that expects the port — which is how the AI Orchestrator
consumes it without changing its own signature.
"""

from __future__ import annotations

import time
from typing import Callable

from pipeline_contracts import Answer, GenerationError, GenerationProvider, LLMRequest

from generation_engine.models import GenerationMetrics, RetryPolicy


class GenerationEngine:
    """Wraps one injected `GenerationProvider`. `sleep` and `metrics_sink` are injectable
    for tests/observability; the last run's metrics are also kept on `last_metrics`."""

    def __init__(
        self,
        provider: GenerationProvider,
        *,
        retry_policy: RetryPolicy | None = None,
        metrics_sink: Callable[[GenerationMetrics], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._provider = provider
        self._policy = retry_policy or RetryPolicy()
        self._metrics_sink = metrics_sink
        self._sleep = sleep
        self.last_metrics: GenerationMetrics | None = None

    @property
    def name(self) -> str:
        return self._provider.name

    def generate(self, request: LLMRequest) -> Answer:
        metrics = GenerationMetrics(provider=self._provider.name)
        started = time.perf_counter()
        try:
            answer = self._execute(request, metrics)
            metrics.succeeded = True
            metrics.model = answer.model
            return answer
        finally:
            metrics.latency_ms = (time.perf_counter() - started) * 1000
            self.last_metrics = metrics
            if self._metrics_sink is not None:
                self._metrics_sink(metrics)

    def _execute(self, request: LLMRequest, metrics: GenerationMetrics) -> Answer:
        attempts = max(1, self._policy.max_attempts)
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self._sleep(self._policy.delay_before(attempt))
                metrics.retries += 1
            metrics.attempts = attempt
            attempt_started = time.perf_counter()
            try:
                answer = self._provider.generate(request)
            except GenerationError as exc:
                metrics.attempt_latencies_ms.append((time.perf_counter() - attempt_started) * 1000)
                if not exc.retryable or attempt == attempts:
                    raise
                metrics.retried_errors.append(type(exc).__name__)
            except Exception as exc:
                # error-translation guard: an adapter let a non-domain exception escape.
                # Never retried (its nature is unknown) and never shown raw to callers.
                metrics.attempt_latencies_ms.append((time.perf_counter() - attempt_started) * 1000)
                raise GenerationError(
                    f"untranslated provider error: {type(exc).__name__}: {exc}",
                    provider=self._provider.name,
                ) from exc
            else:
                metrics.attempt_latencies_ms.append((time.perf_counter() - attempt_started) * 1000)
                return answer
        raise GenerationError("retry loop exhausted", provider=self._provider.name)  # pragma: no cover
