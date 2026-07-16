"""The generation port and its provider-independent error model — the single source of
truth for how the pipeline reaches an LLM.

`GenerationProvider` is the hexagonal port: the Generation Engine wraps it, adapters
(OpenAI today; Claude, Gemini, Ollama, Bedrock tomorrow) implement it, and the AI
Orchestrator depends only on it. It moved here (Phase 12) from `ai_orchestrator.provider`
so both sides share one contract with no circular dependency.

The error hierarchy is the port's failure contract. Adapters translate SDK exceptions into
these domain errors at the boundary; the Generation Engine retries the transient ones
(`retryable = True`); the AI Orchestrator never sees an SDK exception. Pure stdlib — this
module names no provider and imports nothing beyond the sibling contracts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pipeline_contracts.llm import Answer, LLMRequest


# ── the port ──────────────────────────────────────────────────────────────────
@runtime_checkable
class GenerationProvider(Protocol):
    """Turns a provider-agnostic `LLMRequest` into an `Answer`. How it authenticates,
    which SDK it uses, and which model family it talks to is entirely the adapter's
    business — callers never know."""

    @property
    def name(self) -> str:
        """Stable provider identifier recorded on every answer for audit ('openai', …)."""
        ...

    def generate(self, request: LLMRequest) -> Answer: ...


# ── the domain error model ────────────────────────────────────────────────────
class GenerationError(Exception):
    """Base of every generation failure the pipeline can see. `retryable` tells the
    Generation Engine whether another attempt could plausibly succeed."""

    retryable: bool = False

    def __init__(self, message: str, *, provider: str = "") -> None:
        super().__init__(message)
        self.provider = provider


class AuthenticationError(GenerationError):
    """Bad or missing credentials / insufficient permissions. Retrying cannot help."""

    retryable = False


class InvalidRequest(GenerationError):
    """The provider rejected the request itself (malformed, too large, unknown model).
    The same request would fail again — never retried."""

    retryable = False


class RateLimitError(GenerationError):
    """The provider throttled us. Transient — retried with backoff."""

    retryable = True


class TimeoutError(GenerationError):  # noqa: A001 - deliberate domain name, always namespaced
    """The call exceeded its time budget. Transient — retried."""

    retryable = True


class ProviderUnavailable(GenerationError):
    """The provider is down or unreachable (5xx, connection failure). Transient — retried."""

    retryable = True
