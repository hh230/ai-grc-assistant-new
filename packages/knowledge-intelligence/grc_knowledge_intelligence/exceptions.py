"""Exceptions raised by the Autonomous Knowledge Engine's pure pipeline."""

from __future__ import annotations


class KnowledgeEngineError(Exception):
    """Base class for every error this package raises."""


class KnowledgeExtractionError(KnowledgeEngineError):
    """A ``KnowledgeExtractorPort`` could not produce a valid ``KnowledgeAnswer`` for a
    question from a given source excerpt (e.g. the excerpt does not actually address the
    question, or the extractor's output failed validation). The engine records this as a
    failed discovery rather than guessing (CLAUDE.md §16: fail safe, not open)."""
