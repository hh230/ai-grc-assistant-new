"""Provider configuration, read from the environment (never hardcoded; never logged).

The API key and model ids come from environment variables (loaded from ``.env`` at deploy time).
``OpenAISettings.from_env`` fails fast with a clear error if the key is absent (CLAUDE.md §22:
no secrets in code).
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from .exceptions import LLMConfigurationError

_DEFAULT_CHAT_MODEL = "gpt-4o-mini"
_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
_DEFAULT_EMBEDDING_DIMENSION = 1536

# Native output dimensions of the known embedding models, used when the dimension is not set
# explicitly so the declared dimension always matches what the provider returns.
_NATIVE_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


@dataclass(frozen=True)
class OpenAISettings:
    """OpenAI provider settings. ``api_key`` is sensitive and must never be logged or printed."""

    api_key: str
    chat_model: str = _DEFAULT_CHAT_MODEL
    embedding_model: str = _DEFAULT_EMBEDDING_MODEL
    embedding_dimension: int = _DEFAULT_EMBEDDING_DIMENSION
    base_url: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> OpenAISettings:
        environ: Mapping[str, str] = os.environ if env is None else env
        api_key = environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is not set; provide it via the environment (.env)"
            )
        embedding_model = environ.get("OPENAI_EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL)
        explicit_dimension = environ.get("OPENAI_EMBEDDING_DIMENSION")
        embedding_dimension = (
            int(explicit_dimension)
            if explicit_dimension
            else _NATIVE_EMBEDDING_DIMENSIONS.get(embedding_model, _DEFAULT_EMBEDDING_DIMENSION)
        )
        return cls(
            api_key=api_key,
            # ``OPENAI_MODEL`` is the canonical name; ``OPENAI_CHAT_MODEL`` is accepted as an alias.
            chat_model=(
                environ.get("OPENAI_MODEL")
                or environ.get("OPENAI_CHAT_MODEL")
                or _DEFAULT_CHAT_MODEL
            ),
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            base_url=environ.get("OPENAI_BASE_URL") or None,
        )

    def __repr__(self) -> str:  # never leak the key in logs/tracebacks
        return (
            f"OpenAISettings(chat_model={self.chat_model!r}, "
            f"embedding_model={self.embedding_model!r}, api_key=***)"
        )
