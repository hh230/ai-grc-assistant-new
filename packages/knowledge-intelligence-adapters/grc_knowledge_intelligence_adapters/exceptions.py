"""Exceptions raised by the Knowledge Intelligence adapters."""

from __future__ import annotations


class KnowledgeSynthesisRejectedError(Exception):
    """The synthesis Tool's LLM call returned output that was not valid JSON, or did not
    match the required schema (an empty answer, a confidence outside [0, 1], ...). Rejected
    here, before it can ever become a stored ``KnowledgeItem`` (CLAUDE.md §12.6:
    uncited/unvalidated claims are rejected, not guessed at)."""
