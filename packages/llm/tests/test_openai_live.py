"""Opt-in live smoke tests for the real OpenAI adapter.

These make real (paid) API calls and are skipped unless both ``OPENAI_API_KEY`` and
``RUN_LLM_LIVE_TESTS=1`` are set — so the automated gates never call the network or incur cost
(CLAUDE.md §22: live/eval suites run separately from unit tests).
"""
from __future__ import annotations

import os

import pytest
from grc_llm import (
    ChatMessage,
    ChatRequest,
    OpenAIChatModel,
    OpenAIEmbeddingModel,
    OpenAISettings,
)

_LIVE_ENABLED = os.environ.get("RUN_LLM_LIVE_TESTS") == "1" and bool(
    os.environ.get("OPENAI_API_KEY")
)
pytestmark = pytest.mark.skipif(
    not _LIVE_ENABLED,
    reason="set RUN_LLM_LIVE_TESTS=1 and OPENAI_API_KEY to run live OpenAI tests",
)


async def test_openai_chat_smoke() -> None:
    model = OpenAIChatModel(OpenAISettings.from_env())
    # A generous budget so reasoning models (which spend hidden tokens) still return visible text.
    result = await model.complete(
        ChatRequest(
            messages=(ChatMessage.user("Reply with exactly the word: ok"),),
            max_output_tokens=256,
        )
    )
    assert result.text.strip() != ""
    assert result.usage.total_tokens > 0


async def test_openai_embedding_smoke() -> None:
    model = OpenAIEmbeddingModel(OpenAISettings.from_env())
    result = await model.embed(["asset inventory"])
    assert result.dimension == model.dimension
    assert len(result.vectors) == 1
