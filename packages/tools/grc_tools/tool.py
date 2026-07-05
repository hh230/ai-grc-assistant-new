"""The Tool contract (CLAUDE.md §9): a schema-validated, independently callable capability.

A ``Tool`` does one cohesive thing, declares its side-effect profile via a
``grc_domain.platform.ToolDescriptor``, and is invoked identically by any of the six callers
in ``grc_tools.context.ToolCaller``. Concrete tools depend on the Services layer for any
domain coordination (CLAUDE.md §14) — never on a route handler, a specific UI, or an LLM SDK
directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from grc_domain.platform import ToolDescriptor
from pydantic import BaseModel

from .context import ToolContext

TIn = TypeVar("TIn", bound=BaseModel)
TOut = TypeVar("TOut", bound=BaseModel)


@dataclass(frozen=True)
class ToolOutcome(Generic[TOut]):
    """What a Tool produced, plus everything the audit trail needs (CLAUDE.md §19).

    All grounding/usage fields are optional: a pure data-query tool (e.g. scanning coverage
    gaps from already-stored data) has no model/tokens to report; an LLM-backed tool
    (e.g. drafting a policy) populates them.
    """

    output: TOut
    confidence: float | None = None
    citations: tuple[str, ...] = ()
    model: str | None = None
    prompt_version: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None


class Tool(ABC, Generic[TIn, TOut]):
    """A first-class, independently callable business capability."""

    @property
    @abstractmethod
    def descriptor(self) -> ToolDescriptor:
        """The governance descriptor: name, version, side effect, required permissions."""

    @property
    @abstractmethod
    def input_model(self) -> type[TIn]:
        """The Pydantic model inputs are validated against before ``run`` is called."""

    @property
    @abstractmethod
    def output_model(self) -> type[TOut]:
        """The Pydantic model the outcome's ``output`` is validated against."""

    @abstractmethod
    async def run(self, input: TIn, context: ToolContext) -> ToolOutcome[TOut]: ...
