"""grc_llm — the provider-agnostic LLM abstraction (CLAUDE.md §4).

Business logic, agents, and the orchestrator depend on the ``ChatModel`` / ``EmbeddingModel`` ports
and the provider-agnostic value objects here — never on a vendor SDK. The concrete OpenAI adapter
(the only module importing ``openai``) is injected at the composition root; deterministic fakes
back the automated test gates.
"""
from __future__ import annotations

from .exceptions import (
    LLMConfigurationError,
    LLMError,
    LLMProviderError,
    LLMResponseError,
)
from .fake import FakeChatModel, FakeEmbeddingModel
from .models import (
    ChatMessage,
    ChatRequest,
    ChatResult,
    EmbeddingResult,
    Role,
    TokenUsage,
)
from .openai_provider import OpenAIChatModel, OpenAIEmbeddingModel
from .ports import ChatModel, EmbeddingModel
from .settings import OpenAISettings

__all__ = [
    # ports
    "ChatModel",
    "EmbeddingModel",
    # models
    "ChatMessage",
    "ChatRequest",
    "ChatResult",
    "EmbeddingResult",
    "Role",
    "TokenUsage",
    # providers
    "OpenAIChatModel",
    "OpenAIEmbeddingModel",
    "OpenAISettings",
    "FakeChatModel",
    "FakeEmbeddingModel",
    # exceptions
    "LLMError",
    "LLMConfigurationError",
    "LLMProviderError",
    "LLMResponseError",
]
