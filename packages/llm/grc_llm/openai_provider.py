"""The OpenAI adapter — the **only** module that imports the OpenAI SDK (CLAUDE.md §4).

It implements the provider-agnostic ports against ``openai.AsyncOpenAI``, applies per-call budgets
(timeout, max output tokens), records token usage and latency for audit, and translates SDK errors
into ``LLMProviderError``. The API key is read from ``OpenAISettings`` (env-sourced) and never
logged. Swapping providers means writing another adapter — no business code changes.
"""
from __future__ import annotations

import time
from collections.abc import Sequence

from openai import AsyncOpenAI, Omit, OpenAIError, omit
from openai.types.chat import ChatCompletionMessageParam

from .exceptions import LLMProviderError, LLMResponseError
from .models import ChatMessage, ChatRequest, ChatResult, EmbeddingResult, Role, TokenUsage
from .ports import ChatModel, EmbeddingModel
from .settings import OpenAISettings


class OpenAIChatModel(ChatModel):
    """Chat completions via OpenAI."""

    def __init__(self, settings: OpenAISettings, *, client: AsyncOpenAI | None = None) -> None:
        self._settings = settings
        self._client = client or AsyncOpenAI(api_key=settings.api_key, base_url=settings.base_url)

    @property
    def model(self) -> str:
        return self._settings.chat_model

    async def complete(self, request: ChatRequest) -> ChatResult:
        messages = [_to_message_param(message) for message in request.messages]
        # Newer models use ``max_completion_tokens``; reasoning models (o-series, GPT-5) only allow
        # the default temperature, so omit it for them.
        temperature: float | Omit = (
            request.temperature if _supports_custom_temperature(self._settings.chat_model) else omit
        )
        started = time.monotonic()
        try:
            if request.json_object:
                response = await self._client.chat.completions.create(
                    model=self._settings.chat_model,
                    messages=messages,
                    max_completion_tokens=request.max_output_tokens,
                    temperature=temperature,
                    timeout=request.timeout_seconds,
                    response_format={"type": "json_object"},
                )
            else:
                response = await self._client.chat.completions.create(
                    model=self._settings.chat_model,
                    messages=messages,
                    max_completion_tokens=request.max_output_tokens,
                    temperature=temperature,
                    timeout=request.timeout_seconds,
                )
        except OpenAIError as exc:
            raise LLMProviderError(f"OpenAI chat call failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        if not response.choices:
            raise LLMResponseError("OpenAI returned no choices")
        choice = response.choices[0]
        content = choice.message.content
        if content is None:
            raise LLMResponseError("OpenAI returned no message content")
        return ChatResult(
            text=content,
            model=response.model,
            usage=_usage(response.usage),
            finish_reason=choice.finish_reason,
            latency_ms=latency_ms,
        )


class OpenAIEmbeddingModel(EmbeddingModel):
    """Embeddings via OpenAI."""

    def __init__(self, settings: OpenAISettings, *, client: AsyncOpenAI | None = None) -> None:
        self._settings = settings
        self._client = client or AsyncOpenAI(api_key=settings.api_key, base_url=settings.base_url)

    @property
    def model(self) -> str:
        return self._settings.embedding_model

    @property
    def dimension(self) -> int:
        return self._settings.embedding_dimension

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=(), model=self._settings.embedding_model)
        # The 3-* models accept ``dimensions`` to pin the output size to the declared dimension.
        dimensions: int | Omit = (
            self._settings.embedding_dimension
            if self._settings.embedding_model.startswith("text-embedding-3")
            else omit
        )
        try:
            response = await self._client.embeddings.create(
                model=self._settings.embedding_model,
                input=list(texts),
                dimensions=dimensions,
            )
        except OpenAIError as exc:
            raise LLMProviderError(f"OpenAI embedding call failed: {exc}") from exc
        vectors = tuple(tuple(item.embedding) for item in response.data)
        return EmbeddingResult(vectors=vectors, model=response.model, usage=_usage(response.usage))


def _supports_custom_temperature(model: str) -> bool:
    """Reasoning models (o-series, GPT-5 family) only allow the default temperature."""
    lowered = model.lower()
    return not lowered.startswith(("o1", "o3", "o4", "gpt-5"))


def _to_message_param(message: ChatMessage) -> ChatCompletionMessageParam:
    if message.role is Role.SYSTEM:
        return {"role": "system", "content": message.content}
    if message.role is Role.USER:
        return {"role": "user", "content": message.content}
    return {"role": "assistant", "content": message.content}


def _usage(raw: object) -> TokenUsage:
    prompt = getattr(raw, "prompt_tokens", 0) or 0
    completion = getattr(raw, "completion_tokens", 0) or 0
    return TokenUsage(prompt_tokens=int(prompt), completion_tokens=int(completion))
