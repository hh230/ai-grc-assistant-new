"""Provider-agnostic value objects for chat and embedding calls.

These are the only shapes business logic sees — never a vendor SDK type (CLAUDE.md §4). Every
result carries the model id and token usage so each call is auditable (CLAUDE.md §19, §22).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    """The author of a chat message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ChatMessage:
    """One message in a chat exchange."""

    role: Role
    content: str

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        return cls(Role.SYSTEM, content)

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        return cls(Role.USER, content)

    @classmethod
    def assistant(cls, content: str) -> ChatMessage:
        return cls(Role.ASSISTANT, content)


@dataclass(frozen=True)
class ChatRequest:
    """A provider-agnostic chat request, including its per-call budget.

    ``json_object`` asks the provider for a structured JSON response (used when the result drives
    logic — CLAUDE.md §22). ``prompt_version`` is recorded for reproducibility.
    """

    messages: tuple[ChatMessage, ...]
    max_output_tokens: int = 1024
    temperature: float = 0.0
    timeout_seconds: float = 30.0
    json_object: bool = False
    prompt_version: str | None = None

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("ChatRequest must contain at least one message")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be > 0")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be within [0, 2]")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")


@dataclass(frozen=True)
class TokenUsage:
    """Token accounting for a single call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class ChatResult:
    """The provider-agnostic result of a chat call."""

    text: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    """One or more embedding vectors, with the model and usage that produced them."""

    vectors: tuple[tuple[float, ...], ...]
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)

    @property
    def dimension(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0
