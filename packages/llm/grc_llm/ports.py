"""The LLM provider ports — the swappable seam between business logic and any vendor SDK.

Business logic, agents, and the orchestrator depend only on these abstractions; the concrete
provider (OpenAI, …) is injected at the composition root (CLAUDE.md §4, §7). Calls are async.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .models import ChatRequest, ChatResult, EmbeddingResult


class ChatModel(ABC):
    """A chat-completion model behind a provider-agnostic interface."""

    @property
    @abstractmethod
    def model(self) -> str:
        """The concrete model identifier (recorded for audit)."""

    @abstractmethod
    async def complete(self, request: ChatRequest) -> ChatResult: ...


class EmbeddingModel(ABC):
    """An embedding model behind a provider-agnostic interface."""

    @property
    @abstractmethod
    def model(self) -> str: ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """The fixed dimension of vectors this model produces."""

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> EmbeddingResult: ...
