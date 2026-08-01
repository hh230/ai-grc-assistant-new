"""The Generation Engine's own small models: the retry policy and the execution metrics.

`GenerationMetrics` records only what no other layer can see — attempt-level detail
(attempts, retries, per-attempt latency, the errors that triggered retries). Token usage
already lives on the `Answer`, and stage-level timing already lives in the AI Orchestrator's
`PipelineMetrics`; neither is duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline_contracts import dataclass_dict


@dataclass(frozen=True)
class RetryPolicy:
    """How the engine retries *retryable* domain errors (RateLimitError, TimeoutError,
    ProviderUnavailable). Non-retryable errors (AuthenticationError, InvalidRequest) are
    raised immediately regardless of this policy."""

    max_attempts: int = 3
    backoff_base_seconds: float = 0.5
    backoff_multiplier: float = 2.0

    def delay_before(self, attempt: int) -> float:
        """Backoff before the given (2-based) attempt: base · multiplier^(attempt-2)."""
        return self.backoff_base_seconds * (self.backoff_multiplier ** (attempt - 2))


@dataclass
class GenerationMetrics:
    """One execution's observability record."""

    provider: str = ""
    model: str = ""
    attempts: int = 0
    retries: int = 0
    latency_ms: float = 0.0
    attempt_latencies_ms: list[float] = field(default_factory=list)
    retried_errors: list[str] = field(default_factory=list)
    succeeded: bool = False

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(
            self,
            extra={
                "latency_ms": round(self.latency_ms, 2),
                "attempt_latencies_ms": [round(v, 2) for v in self.attempt_latencies_ms],
            },
        )
