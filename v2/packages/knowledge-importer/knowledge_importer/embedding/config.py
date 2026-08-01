"""Embedding configuration — all provider selection and tuning lives here, sourced from
the environment with sensible defaults. No API key ever appears in this file or in the
resulting config object; the key is read by the provider from the environment at call
time (see `providers/openai_provider.py`).

`embedding_version` is the manual lever for forcing a full re-embed: bump it and every
chunk is regenerated on the next run even if its text and model are unchanged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_PROVIDER = "local"
DEFAULT_MODEL = "local-deterministic-hash-v1"
DEFAULT_DIMENSION = 1536
DEFAULT_BATCH_SIZE = 64
DEFAULT_MAX_RETRIES = 4
DEFAULT_RETRY_BASE_DELAY = 0.5
EMBEDDING_VERSION = "v1"


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    dimension: int = DEFAULT_DIMENSION
    batch_size: int = DEFAULT_BATCH_SIZE
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    embedding_version: str = EMBEDDING_VERSION

    def fingerprint(self) -> dict[str, object]:
        """The config identity a checkpoint is keyed on. If any of these change, a
        resumed run must not blindly trust prior progress — the skip logic re-checks
        every chunk against model + version anyway, so this is a fast-path guard, not the
        correctness mechanism."""
        return {
            "provider": self.provider,
            "model": self.model,
            "dimension": self.dimension,
            "embedding_version": self.embedding_version,
        }


def config_from_env() -> EmbeddingConfig:
    """Build config from environment variables, falling back to the local provider so the
    engine runs end-to-end with no credentials. Switching to a real vendor is purely
    environment: e.g. EMBEDDING_PROVIDER=openai EMBEDDING_MODEL=text-embedding-3-large
    (plus OPENAI_API_KEY, read by the provider itself)."""
    provider = os.environ.get("EMBEDDING_PROVIDER", DEFAULT_PROVIDER)
    # Default the model to a provider-appropriate value when the caller didn't pin one.
    default_model = "text-embedding-3-large" if provider.lower() == "openai" else DEFAULT_MODEL
    return EmbeddingConfig(
        provider=provider,
        model=os.environ.get("EMBEDDING_MODEL", default_model),
        dimension=int(os.environ.get("EMBEDDING_DIMENSION", DEFAULT_DIMENSION)),
        batch_size=int(os.environ.get("EMBEDDING_BATCH_SIZE", DEFAULT_BATCH_SIZE)),
        max_retries=int(os.environ.get("EMBEDDING_MAX_RETRIES", DEFAULT_MAX_RETRIES)),
        retry_base_delay=float(os.environ.get("EMBEDDING_RETRY_BASE_DELAY", DEFAULT_RETRY_BASE_DELAY)),
        embedding_version=os.environ.get("EMBEDDING_VERSION", EMBEDDING_VERSION),
    )
