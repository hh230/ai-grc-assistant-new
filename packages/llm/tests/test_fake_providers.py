"""Unit tests for the provider-agnostic models and the deterministic fake providers."""
from __future__ import annotations

import pytest
from grc_llm import (
    ChatMessage,
    ChatRequest,
    FakeChatModel,
    FakeEmbeddingModel,
    Role,
)


def request(text: str = "hello", *, json_object: bool = False) -> ChatRequest:
    return ChatRequest(
        messages=(ChatMessage.system("You are a GRC assistant."), ChatMessage.user(text)),
        json_object=json_object,
    )


# --- request validation --------------------------------------------------------------------
def test_chat_request_requires_messages() -> None:
    with pytest.raises(ValueError, match="at least one message"):
        ChatRequest(messages=())


def test_chat_request_validates_budget() -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        ChatRequest(messages=(ChatMessage.user("x"),), max_output_tokens=0)
    with pytest.raises(ValueError, match="temperature"):
        ChatRequest(messages=(ChatMessage.user("x"),), temperature=3.0)


def test_message_role_helpers() -> None:
    assert ChatMessage.system("s").role is Role.SYSTEM
    assert ChatMessage.user("u").role is Role.USER
    assert ChatMessage.assistant("a").role is Role.ASSISTANT


# --- fake chat model -----------------------------------------------------------------------
async def test_fake_chat_returns_scripted_then_default() -> None:
    model = FakeChatModel(responses=["first", "second"], default_response="fallback")
    assert (await model.complete(request())).text == "first"
    assert (await model.complete(request())).text == "second"
    assert (await model.complete(request())).text == "fallback"
    assert len(model.requests) == 3


async def test_fake_chat_records_usage_and_model() -> None:
    model = FakeChatModel(responses=["one two three"], model="fake-x")
    result = await model.complete(request("alpha beta"))
    assert result.model == "fake-x"
    assert result.usage.completion_tokens == 3
    assert result.usage.total_tokens == result.usage.prompt_tokens + 3


# --- fake embedding model ------------------------------------------------------------------
async def test_fake_embeddings_are_deterministic_and_normalized() -> None:
    model = FakeEmbeddingModel(dimension=64)
    first = await model.embed(["asset inventory management"])
    second = await model.embed(["asset inventory management"])
    assert first.vectors == second.vectors  # deterministic
    assert first.dimension == 64
    norm = sum(value * value for value in first.vectors[0]) ** 0.5
    assert norm == pytest.approx(1.0)


async def test_fake_embeddings_place_similar_text_closer() -> None:
    model = FakeEmbeddingModel(dimension=128)
    result = await model.embed(
        [
            "the organization shall maintain an asset inventory",
            "an asset inventory must be maintained by the organization",
            "encryption keys are rotated every ninety days",
        ]
    )
    related = _cosine(result.vectors[0], result.vectors[1])
    unrelated = _cosine(result.vectors[0], result.vectors[2])
    assert related > unrelated


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))
