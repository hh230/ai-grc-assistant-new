"""Grounded answers: parse and **validate** the model's structured output against the context.

Enforces the grounding contract (CLAUDE.md §12.3, §19): every citation must reference a passage
that was actually retrieved; an answer with no valid citation is rejected as *insufficient
evidence* rather than surfaced. The raw model text is treated as untrusted input.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from grc_domain.shared.identifiers import KnowledgeObjectId, KnowledgeSourceVersionId
from grc_llm import TokenUsage

from .retrieval import RetrievalContext

_INSUFFICIENT_MESSAGE = "Insufficient evidence in the provided sources to answer this question."


@dataclass(frozen=True)
class Citation:
    """A grounded citation back to a retrieved knowledge object and its source location."""

    object_id: KnowledgeObjectId
    source_version_id: KnowledgeSourceVersionId
    anchor: str | None


@dataclass(frozen=True)
class GroundedAnswer:
    """A validated, cited answer — or an explicit 'insufficient evidence' result."""

    query: str
    answer: str
    citations: tuple[Citation, ...]
    confidence: float
    model: str
    insufficient_evidence: bool
    usage: TokenUsage = field(default_factory=TokenUsage)

    @classmethod
    def insufficient(
        cls, query: str, *, model: str, usage: TokenUsage | None = None
    ) -> GroundedAnswer:
        return cls(
            query=query,
            answer=_INSUFFICIENT_MESSAGE,
            citations=(),
            confidence=0.0,
            model=model,
            insufficient_evidence=True,
            usage=usage if usage is not None else TokenUsage(),
        )


def parse_and_validate(
    raw_text: str, context: RetrievalContext, *, model: str, usage: TokenUsage
) -> GroundedAnswer:
    """Validate the model's JSON output against the retrieved context; fail safe to insufficient."""
    data = _load_json(raw_text)
    if data is None:
        return GroundedAnswer.insufficient(context.query, model=model, usage=usage)

    answer = str(data.get("answer", "")).strip()
    confidence = _coerce_confidence(data.get("confidence"))
    by_key = {str(chunk.object_id): chunk for chunk in context.chunks}

    citations: list[Citation] = []
    raw_citations = data.get("citations", [])
    if isinstance(raw_citations, list):
        for key in raw_citations:
            chunk = by_key.get(str(key))
            if chunk is not None and not any(c.object_id == chunk.object_id for c in citations):
                citations.append(
                    Citation(
                        object_id=chunk.object_id,
                        source_version_id=chunk.source_version_id,
                        anchor=chunk.anchor,
                    )
                )

    # Grounding guarantee: no answer, or no valid citation, → reject as insufficient evidence.
    if not answer or not citations:
        return GroundedAnswer.insufficient(context.query, model=model, usage=usage)

    return GroundedAnswer(
        query=context.query,
        answer=answer,
        citations=tuple(citations),
        confidence=confidence,
        model=model,
        insufficient_evidence=False,
        usage=usage,
    )


def _load_json(raw_text: str) -> Mapping[str, object] | None:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _coerce_confidence(value: object) -> float:
    if isinstance(value, bool):  # bool is an int subclass; reject it explicitly
        return 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    return 0.0
