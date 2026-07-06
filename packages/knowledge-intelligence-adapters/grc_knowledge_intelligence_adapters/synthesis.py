"""The LLM synthesizer: a first-class ``grc_tools.Tool`` plus the ``KnowledgeExtractorPort``
adapter that calls it *through the Tool Registry* — so every synthesis call is authorized,
validated, and unconditionally audited exactly like any other Tool invocation (CLAUDE.md §9,
§19), never a raw, unaudited LLM SDK call from business logic (CLAUDE.md §7). Mirrors
``grc_regulatory_intelligence_adapters.classification``'s structure exactly.
"""

from __future__ import annotations

import json

from grc_domain.platform import Permission, ToolDescriptor, ToolSideEffect
from grc_domain.shared.identifiers import ToolId
from grc_domain.shared.value_objects import SemanticVersion
from grc_knowledge_intelligence import (
    KnowledgeAnswer,
    KnowledgeExtractionError,
    KnowledgeExtractorPort,
    KnowledgeQuestion,
    SourceExcerpt,
)
from grc_llm import ChatMessage, ChatModel, ChatRequest
from grc_tools import (
    Tool,
    ToolContext,
    ToolInputValidationError,
    ToolOutcome,
    ToolPermissionDeniedError,
    ToolRegistry,
)
from pydantic import BaseModel, ValidationError, field_validator

from .exceptions import KnowledgeSynthesisRejectedError
from .prompts import (
    SYNTHESIZE_KNOWLEDGE_ANSWER_SYSTEM,
    SYNTHESIZE_KNOWLEDGE_ANSWER_VERSION,
    build_user_prompt,
)

TOOL_NAME = "synthesize_knowledge_answer"
TOOL_VERSION = "1.0.0"

# A source excerpt that plainly does not address the question yields this floor — treated by
# the adapter as "could not ground an answer here", never stored as a KnowledgeItem.
_NOT_GROUNDED_CONFIDENCE = 0.0


class SynthesizeKnowledgeAnswerInput(BaseModel):
    """Tool input: the question plus one trusted source excerpt, for grounding the prompt.
    Deliberately plain strings, not ``grc_knowledge_intelligence`` domain types — Tools are a
    schema-validated boundary (CLAUDE.md §9), not a place to leak internal value objects."""

    question_text: str
    source_excerpt_text: str
    source_id: str


class _RawSynthesisPayload(BaseModel):
    """The LLM's own JSON, validated strictly. Any field missing or out of range raises
    ``ValidationError`` — malformed output is rejected here, before it ever becomes a
    candidate ``KnowledgeItem``."""

    answer: str
    applicable_context: str
    confidence: float

    @field_validator("answer", "applicable_context")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @field_validator("confidence")
    @classmethod
    def _confidence_in_range(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be within [0, 1]")
        return value


class SynthesizeKnowledgeAnswerOutput(BaseModel):
    """Tool output: the validated answer plus the model/prompt provenance that produced it,
    so a caller can reconstruct full grounding from ``ToolRegistry.invoke``'s return value
    alone, without reaching back into the audit log."""

    answer: str
    applicable_context: str
    confidence: float
    model: str
    prompt_version: str


class SynthesizeKnowledgeAnswerTool(
    Tool[SynthesizeKnowledgeAnswerInput, SynthesizeKnowledgeAnswerOutput]
):
    """Synthesizes a candidate answer to one question from one trusted source excerpt via the
    provider-agnostic ``ChatModel``. Read-only (no side effects) — it only proposes an answer;
    nothing is persisted here, and no code path in this Tool ever writes a ``KnowledgeItem``
    or changes its verification status."""

    def __init__(self, chat: ChatModel) -> None:
        self._chat = chat
        self._descriptor = ToolDescriptor.register(
            id=ToolId("synthesize-knowledge-answer"),
            name=TOOL_NAME,
            version=SemanticVersion.parse(TOOL_VERSION),
            description=(
                "Synthesizes a candidate answer to one GRC/compliance/legal question from one "
                "trusted source excerpt, with a confidence score."
            ),
            side_effect=ToolSideEffect.READ_ONLY,
            required_permissions=frozenset({Permission("knowledge_intelligence")}),
        )

    @property
    def descriptor(self) -> ToolDescriptor:
        return self._descriptor

    @property
    def input_model(self) -> type[SynthesizeKnowledgeAnswerInput]:
        return SynthesizeKnowledgeAnswerInput

    @property
    def output_model(self) -> type[SynthesizeKnowledgeAnswerOutput]:
        return SynthesizeKnowledgeAnswerOutput

    async def run(
        self, input: SynthesizeKnowledgeAnswerInput, context: ToolContext
    ) -> ToolOutcome[SynthesizeKnowledgeAnswerOutput]:
        request = ChatRequest(
            messages=(
                ChatMessage.system(SYNTHESIZE_KNOWLEDGE_ANSWER_SYSTEM),
                ChatMessage.user(
                    build_user_prompt(
                        input.question_text,
                        input.source_excerpt_text,
                        source_id=input.source_id,
                    )
                ),
            ),
            json_object=True,
            temperature=0.0,
            prompt_version=SYNTHESIZE_KNOWLEDGE_ANSWER_VERSION,
        )
        result = await self._chat.complete(request)

        try:
            data = json.loads(result.text)
        except json.JSONDecodeError as exc:
            raise KnowledgeSynthesisRejectedError(
                f"synthesizer returned non-JSON output: {exc}"
            ) from exc

        try:
            payload = _RawSynthesisPayload.model_validate(data)
        except ValidationError as exc:
            raise KnowledgeSynthesisRejectedError(
                f"synthesizer returned an invalid answer: {exc}"
            ) from exc

        output = SynthesizeKnowledgeAnswerOutput(
            **payload.model_dump(),
            model=result.model,
            prompt_version=SYNTHESIZE_KNOWLEDGE_ANSWER_VERSION,
        )
        return ToolOutcome(
            output=output,
            confidence=output.confidence,
            model=result.model,
            prompt_version=SYNTHESIZE_KNOWLEDGE_ANSWER_VERSION,
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
        )


class LlmKnowledgeExtractor(KnowledgeExtractorPort):
    """The pure engine's ``KnowledgeExtractorPort``, implemented by invoking
    ``SynthesizeKnowledgeAnswerTool`` through the Tool Registry — the registry authorizes,
    validates, executes, and unconditionally audits the call (including a rejected/failed
    synthesis), exactly as CLAUDE.md §19 requires for every AI action.
    """

    def __init__(self, registry: ToolRegistry, *, context: ToolContext) -> None:
        self._registry = registry
        self._context = context

    async def extract(self, question: KnowledgeQuestion, excerpt: SourceExcerpt) -> KnowledgeAnswer:
        try:
            output = await self._registry.invoke(
                TOOL_NAME,
                TOOL_VERSION,
                {
                    "question_text": question.question,
                    "source_excerpt_text": excerpt.text,
                    "source_id": excerpt.source.source_id,
                },
                self._context,
            )
        except (
            ToolInputValidationError,
            ToolPermissionDeniedError,
            KnowledgeSynthesisRejectedError,
        ) as exc:
            raise KnowledgeExtractionError(str(exc)) from exc

        if not isinstance(output, SynthesizeKnowledgeAnswerOutput):  # pragma: no cover
            raise KnowledgeExtractionError(f"unexpected synthesizer output type: {type(output)!r}")

        if output.confidence <= _NOT_GROUNDED_CONFIDENCE:
            raise KnowledgeExtractionError("the source excerpt does not address this question")

        return KnowledgeAnswer(
            answer=output.answer,
            applicable_context=output.applicable_context,
            confidence=output.confidence,
        )
