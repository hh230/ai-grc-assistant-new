"""Shared SDK→domain error translation for the provider adapters (Claude, Gemini, Ollama).

Every adapter must present the pipeline's single, provider-independent error contract
(`pipeline_contracts.generation`) at its boundary — never a raw SDK exception. The mapping is
by HTTP status code first (works across every httpx-based SDK) and by exception-class *name*
second (so it also works with injected fakes and when the SDK is not importable), exactly the
strategy the OpenAI adapter established. The engine's retry logic keys off the resulting
domain error's `retryable` flag, so translating correctly here is what makes retry correct.

The OpenAI adapter keeps its own copy of this logic unchanged; this module exists for the
adapters added in Phase 13 and takes the provider name as a parameter.
"""

from __future__ import annotations

from pipeline_contracts import (
    AuthenticationError,
    GenerationError,
    InvalidRequest,
    ProviderUnavailable,
    RateLimitError,
)
from pipeline_contracts import TimeoutError as GenerationTimeoutError

# Exception-class name → domain error. Covers the shared httpx hierarchy used by the
# openai/anthropic SDKs plus the google-genai and ollama error class names.
_NAME_TO_DOMAIN: dict[str, type[GenerationError]] = {
    # auth
    "AuthenticationError": AuthenticationError,
    "PermissionDeniedError": AuthenticationError,
    "PermissionDenied": AuthenticationError,
    # throttling
    "RateLimitError": RateLimitError,
    "ResourceExhausted": RateLimitError,
    # timeouts
    "APITimeoutError": GenerationTimeoutError,
    "DeadlineExceeded": GenerationTimeoutError,
    "Timeout": GenerationTimeoutError,
    # unavailable / transient
    "APIConnectionError": ProviderUnavailable,
    "ConnectError": ProviderUnavailable,
    "ConnectionError": ProviderUnavailable,
    "InternalServerError": ProviderUnavailable,
    "ServiceUnavailableError": ProviderUnavailable,
    "ServerError": ProviderUnavailable,
    "Unavailable": ProviderUnavailable,
    # bad request (non-retryable)
    "BadRequestError": InvalidRequest,
    "InvalidArgument": InvalidRequest,
    "ClientError": InvalidRequest,
    "NotFoundError": InvalidRequest,
    "UnprocessableEntityError": InvalidRequest,
}


def _by_status(status: int) -> type[GenerationError] | None:
    if status in (401, 403):
        return AuthenticationError
    if status == 429:
        return RateLimitError
    if status == 408:
        return GenerationTimeoutError
    if status >= 500:
        return ProviderUnavailable
    if status >= 400:
        return InvalidRequest
    return None


def translate_sdk_error(exc: Exception, *, provider: str) -> GenerationError:
    """SDK exception → domain error. Status code wins where present (`status_code`, or
    google-genai's `code`); the class-name map covers connection/timeout errors that carry
    none; the builtin `TimeoutError` is honoured; anything unknown becomes a base
    `GenerationError` (non-retryable — the engine won't hammer an unknown failure)."""
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        status = getattr(exc, "code", None)  # google-genai carries HTTP status on .code

    domain: type[GenerationError] | None = None
    if isinstance(status, int):
        domain = _by_status(status)
    if domain is None:
        domain = _NAME_TO_DOMAIN.get(type(exc).__name__)
    if domain is None and isinstance(exc, TimeoutError):  # the builtin
        domain = GenerationTimeoutError
    if domain is None:
        domain = GenerationError
    return domain(f"{type(exc).__name__}: {exc}", provider=provider)
