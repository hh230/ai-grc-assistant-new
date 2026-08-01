"""The OpenAI adapter for the `GenerationProvider` port (moved here from ai-orchestrator in
Phase 12 — the AI Orchestrator no longer contains any OpenAI knowledge).

This is the only module in the pipeline allowed to know OpenAI exists. The SDK is an
optional dependency (`generation-engine[openai]`) and is imported lazily, so the engine and
its tests never load it; a pre-built client can also be injected, which is how tests
exercise the adapter without the SDK or a network. The API key is never taken as plain
config here — the SDK resolves it from the environment (`OPENAI_API_KEY`), per the
no-secrets-in-code rule.

Error boundary: every SDK exception is translated into the shared provider-independent
domain errors (`pipeline_contracts.generation`) before it leaves this module. Translation
is by HTTP status code and exception-class name rather than by SDK type, so it works with
injected fake clients and without the SDK importable.
"""

from __future__ import annotations

from pipeline_contracts import (
    Answer,
    AuthenticationError,
    GenerationError,
    InvalidRequest,
    LLMRequest,
    ProviderUnavailable,
    RateLimitError,
)
from pipeline_contracts import TimeoutError as GenerationTimeoutError

DEFAULT_MODEL = "gpt-4o-mini"
_FALLBACK_MAX_OUTPUT_TOKENS = 1200
_FALLBACK_TEMPERATURE = 0.2

_PROVIDER = "openai"

# SDK exception-class name → domain error (covers the openai>=1.x hierarchy)
_NAME_TO_DOMAIN: dict[str, type[GenerationError]] = {
    "AuthenticationError": AuthenticationError,
    "PermissionDeniedError": AuthenticationError,
    "RateLimitError": RateLimitError,
    "APITimeoutError": GenerationTimeoutError,
    "APIConnectionError": ProviderUnavailable,
    "InternalServerError": ProviderUnavailable,
    "ServiceUnavailableError": ProviderUnavailable,
    "BadRequestError": InvalidRequest,
    "NotFoundError": InvalidRequest,
    "UnprocessableEntityError": InvalidRequest,
    "ContentFilterFinishReasonError": InvalidRequest,
}


def _translate(exc: Exception) -> GenerationError:
    """SDK exception → domain error. Status code wins where present; exception-class name
    covers connection/timeout errors that carry none; anything unknown is a base
    `GenerationError` (non-retryable — the engine won't blindly hammer an unknown failure)."""
    status = getattr(exc, "status_code", None)
    domain: type[GenerationError] | None = None
    if isinstance(status, int):
        if status in (401, 403):
            domain = AuthenticationError
        elif status == 429:
            domain = RateLimitError
        elif status == 408:
            domain = GenerationTimeoutError
        elif status >= 500:
            domain = ProviderUnavailable
        elif status >= 400:
            domain = InvalidRequest
    if domain is None:
        domain = _NAME_TO_DOMAIN.get(type(exc).__name__)
    if domain is None and isinstance(exc, TimeoutError):  # the builtin (socket/asyncio timeouts)
        domain = GenerationTimeoutError
    if domain is None:
        domain = GenerationError
    return domain(f"{type(exc).__name__}: {exc}", provider=_PROVIDER)


class OpenAIGenerationProvider:
    """`GenerationProvider` adapter over OpenAI chat completions. Maps the request's
    provider-neutral `messages()` fold and `params` (temperature, max_output_tokens) onto
    the SDK call, and maps the SDK response back into the shared `Answer` contract."""

    def __init__(self, *, model: str = DEFAULT_MODEL, client: object | None = None) -> None:
        self._model = model
        self._client = client if client is not None else self._build_client()

    @property
    def name(self) -> str:
        return _PROVIDER

    @staticmethod
    def _build_client() -> object:
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - exercised via tests without the SDK
            raise ImportError(
                "OpenAIGenerationProvider needs the 'openai' package. "
                "Install the optional extra: generation-engine[openai]"
            ) from exc
        return openai.OpenAI()

    def generate(self, request: LLMRequest) -> Answer:
        params = request.params
        try:
            response = self._client.chat.completions.create(  # type: ignore[attr-defined]
                model=self._model,
                messages=request.messages(),
                temperature=float(params.get("temperature", _FALLBACK_TEMPERATURE)),
                max_tokens=int(params.get("max_output_tokens", _FALLBACK_MAX_OUTPUT_TOKENS)),
            )
        except GenerationError:
            raise  # already a domain error (e.g. from a test double)
        except Exception as exc:
            raise _translate(exc) from exc
        choice = response.choices[0]
        usage = getattr(response, "usage", None)
        return Answer(
            text=choice.message.content or "",
            provider=self.name,
            model=getattr(response, "model", self._model),
            finish_reason=choice.finish_reason or "",
            usage={
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            },
        )
