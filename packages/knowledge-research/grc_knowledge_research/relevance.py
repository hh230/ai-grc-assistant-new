"""Deterministic candidate-document ranking — a cheap, reviewable filter that runs *before*
any LLM call, so the coordinator only spends a synthesis attempt on the documents most likely
to address the question (CLAUDE.md §7: the Orchestrator's budget/cost guardrails apply just as
much to a research pipeline's own internal spend).

This is intentionally not semantic search: a simple word-overlap score is enough to separate
"clearly about vendor contracts" from "clearly about something else" among a source's own
discovered links, and it needs neither an embedding model nor the network to run.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from grc_knowledge_intelligence import KnowledgeQuestion

from .models import DiscoveredDocumentRef

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def score_relevance(question_text: str, candidate_text: str) -> float:
    """The fraction of the question's own words that also appear in the candidate text.
    ``0.0`` if either side has no recognizable words at all."""
    question_tokens = _tokenize(question_text)
    if not question_tokens:
        return 0.0
    candidate_tokens = _tokenize(candidate_text)
    if not candidate_tokens:
        return 0.0
    return len(question_tokens & candidate_tokens) / len(question_tokens)


def rank_refs(
    question: KnowledgeQuestion, refs: Sequence[DiscoveredDocumentRef]
) -> tuple[DiscoveredDocumentRef, ...]:
    """Order discovered documents by relevance to the question, most relevant first. Ties
    (including "no overlap at all") keep their original discovery order — a stable sort, never
    a random one, so a plan's document order is reproducible for audit."""
    scored = sorted(
        refs,
        key=lambda ref: score_relevance(question.question, ref.title or ref.url),
        reverse=True,
    )
    return tuple(scored)
