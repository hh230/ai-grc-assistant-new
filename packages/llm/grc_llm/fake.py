"""Deterministic, offline fake providers for tests and no-egress reference use.

``FakeChatModel`` returns scripted (or a default) responses and records the requests it saw;
``FakeEmbeddingModel`` produces deterministic, L2-normalized bag-of-words vectors so that similar
texts are close in cosine space — enough to exercise semantic retrieval without any network. These
are the providers the automated gates use (CLAUDE.md §22: mock LLM/vector calls in unit tests).
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from .models import ChatRequest, ChatResult, EmbeddingResult, TokenUsage
from .ports import ChatModel, EmbeddingModel


class FakeChatModel(ChatModel):
    """A scripted chat model: returns queued responses, then a default. Records every request."""

    def __init__(
        self,
        *,
        responses: Sequence[str] | None = None,
        default_response: str = '{"answer": "", "citations": [], "confidence": 0.0}',
        model: str = "fake-chat",
    ) -> None:
        self._responses = list(responses or [])
        self._default_response = default_response
        self._model = model
        self.requests: list[ChatRequest] = []

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, request: ChatRequest) -> ChatResult:
        index = len(self.requests)
        self.requests.append(request)
        text = self._responses[index] if index < len(self._responses) else self._default_response
        prompt_tokens = sum(len(message.content.split()) for message in request.messages)
        return ChatResult(
            text=text,
            model=self._model,
            usage=TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=len(text.split())),
            finish_reason="stop",
            latency_ms=0,
        )


class FakeEmbeddingModel(EmbeddingModel):
    """Deterministic bag-of-words embeddings (hash-bucketed, L2-normalized)."""

    def __init__(self, *, dimension: int = 64, model: str = "fake-embed") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be > 0")
        self._dimension = dimension
        self._model = model
        self.requests: list[list[str]] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        self.requests.append(list(texts))
        vectors = tuple(self._vector(text) for text in texts)
        prompt_tokens = sum(len(text.split()) for text in texts)
        return EmbeddingResult(
            vectors=vectors, model=self._model, usage=TokenUsage(prompt_tokens=prompt_tokens)
        )

    def _vector(self, text: str) -> tuple[float, ...]:
        weights = [0.0] * self._dimension
        for token in text.lower().split():
            weights[_bucket(token, self._dimension)] += 1.0
        norm = math.sqrt(sum(weight * weight for weight in weights)) or 1.0
        return tuple(weight / norm for weight in weights)


def _bucket(token: str, dimension: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dimension
