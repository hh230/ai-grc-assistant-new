"""Builds an `EmbeddingProvider` from configuration. This is the single place a provider
name maps to an implementation — adding Voyage/Gemini/BGE/Nomic/Ollama means adding one
branch here plus the provider module. The engine only ever sees the `EmbeddingProvider`
protocol, never a concrete vendor class."""

from __future__ import annotations

from knowledge_importer.embedding.providers.base import EmbeddingProvider
from knowledge_importer.embedding.providers.local import LocalDeterministicProvider
from knowledge_importer.embedding.providers.openai_provider import OpenAIEmbeddingProvider


def build_provider(provider_name: str, model: str, dimension: int) -> EmbeddingProvider:
    name = provider_name.lower()
    if name == "local":
        return LocalDeterministicProvider(model=model, dimension=dimension)
    if name == "openai":
        return OpenAIEmbeddingProvider(model=model, dimension=dimension)
    raise ValueError(
        f"unknown embedding provider {provider_name!r}. Known providers: 'local', 'openai'. "
        f"Add new providers in embedding/providers/ and register them here."
    )
