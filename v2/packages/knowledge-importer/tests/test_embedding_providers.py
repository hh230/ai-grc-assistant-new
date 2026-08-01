from __future__ import annotations

import math

import pytest

from knowledge_importer.embedding.providers import build_provider
from knowledge_importer.embedding.providers.local import LocalDeterministicProvider
from knowledge_importer.embedding.providers.openai_provider import OpenAIConfigError, OpenAIEmbeddingProvider


def test_local_provider_is_deterministic_and_correct_dimension() -> None:
    provider = LocalDeterministicProvider(dimension=32)
    a = provider.embed_batch(["access control policy"])[0]
    b = provider.embed_batch(["access control policy"])[0]
    c = provider.embed_batch(["risk assessment"])[0]
    assert a == b  # same text -> same vector
    assert a != c  # different text -> different vector
    assert len(a) == 32
    assert math.isclose(math.sqrt(sum(x * x for x in a)), 1.0, rel_tol=1e-6)  # L2-normalized


def test_local_provider_batch_order_preserved() -> None:
    provider = LocalDeterministicProvider(dimension=16)
    texts = ["one", "two", "three"]
    vectors = provider.embed_batch(texts)
    assert len(vectors) == 3
    # each is the same as embedding that single text alone
    for text, vector in zip(texts, vectors):
        assert provider.embed_batch([text])[0] == vector


def test_registry_builds_known_providers() -> None:
    assert build_provider("local", "m", 4).name == "local"
    assert build_provider("openai", "text-embedding-3-large", 1536).name == "openai"
    with pytest.raises(ValueError):
        build_provider("voyage", "m", 4)


def test_openai_provider_uses_injected_transport_and_orders_by_index() -> None:
    captured: dict[str, object] = {}

    def fake_transport(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        # return out of order to prove the provider re-sorts by index
        return {"data": [{"index": 1, "embedding": [0.4, 0.5]}, {"index": 0, "embedding": [0.1, 0.2]}]}

    provider = OpenAIEmbeddingProvider(dimension=2, transport=fake_transport, api_key_env="TEST_KEY_VAR")
    import os

    os.environ["TEST_KEY_VAR"] = "sk-test"
    try:
        vectors = provider.embed_batch(["a", "b"])
    finally:
        del os.environ["TEST_KEY_VAR"]

    assert vectors == [[0.1, 0.2], [0.4, 0.5]]  # re-ordered to match input order
    assert captured["payload"]["model"] == "text-embedding-3-large"
    assert captured["payload"]["dimensions"] == 2
    assert captured["headers"]["Authorization"] == "Bearer sk-test"


def test_openai_provider_raises_clear_error_without_key() -> None:
    provider = OpenAIEmbeddingProvider(api_key_env="DEFINITELY_UNSET_KEY_VAR")
    with pytest.raises(OpenAIConfigError):
        provider.embed_batch(["x"])
