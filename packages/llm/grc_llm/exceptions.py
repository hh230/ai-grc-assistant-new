"""Errors for the LLM provider abstraction."""
from __future__ import annotations


class LLMError(Exception):
    """Base class for LLM-layer errors."""


class LLMConfigurationError(LLMError):
    """Raised when a provider is misconfigured (e.g. a missing API key)."""


class LLMProviderError(LLMError):
    """Raised when the underlying provider call fails (network, API error, etc.)."""


class LLMResponseError(LLMError):
    """Raised when a provider returns an unusable response (empty / malformed)."""
