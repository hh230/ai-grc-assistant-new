"""The RAG pipeline: retrieve grounded context, then generate a validated, cited answer.

Composes M10 retrieval with an injected ``ChatModel`` (provider-agnostic). It retrieves the
grounded context, asks the model — constrained to that context, in JSON mode — for an answer with
citations, and validates the result before returning it. If nothing is retrieved, it returns
'insufficient evidence' without calling the model. The LLM never touches the database and never
acts; it only proposes text the pipeline validates (CLAUDE.md §7, §12).
"""
from __future__ import annotations

from grc_llm import ChatMessage, ChatModel, ChatRequest, TokenUsage

from .generation import GroundedAnswer, parse_and_validate
from .prompts import ANSWER_QUESTION_SYSTEM, ANSWER_QUESTION_VERSION, build_user_prompt
from .retrieval import KnowledgeRetriever


class RagPipeline:
    """Retrieve-then-generate over a tenant's knowledge, with grounded, validated output."""

    def __init__(
        self,
        retriever: KnowledgeRetriever,
        chat: ChatModel,
        *,
        top_k: int = 5,
        max_context_chars: int = 4000,
        max_output_tokens: int = 512,
    ) -> None:
        self._retriever = retriever
        self._chat = chat
        self._top_k = top_k
        self._max_context_chars = max_context_chars
        self._max_output_tokens = max_output_tokens

    async def answer(self, query: str) -> GroundedAnswer:
        context = self._retriever.retrieve(
            query, top_k=self._top_k, max_total_chars=self._max_context_chars
        )
        if context.is_empty:
            return GroundedAnswer.insufficient(query, model=self._chat.model, usage=TokenUsage())

        request = ChatRequest(
            messages=(
                ChatMessage.system(ANSWER_QUESTION_SYSTEM),
                ChatMessage.user(build_user_prompt(query, context.grounded_text())),
            ),
            max_output_tokens=self._max_output_tokens,
            temperature=0.0,
            json_object=True,
            prompt_version=ANSWER_QUESTION_VERSION,
        )
        result = await self._chat.complete(request)
        return parse_and_validate(result.text, context, model=result.model, usage=result.usage)
