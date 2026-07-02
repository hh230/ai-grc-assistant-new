"""Enumerations for the extraction engine's application layer."""
from __future__ import annotations

from enum import Enum


class ExtractorTechnique(str, Enum):
    """How an extractor produces candidates. Rule-based now; AI-assisted later — the engine
    treats them identically behind the same port."""

    RULE = "rule"
    AI = "ai"


class BlockKind(str, Enum):
    """The kind of a parsed layout block (the adapter's structural signal)."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    FOOTNOTE = "footnote"
    CAPTION = "caption"
    OTHER = "other"


class SegmentRole(str, Enum):
    """The functional role of a segment, used to route the right extractors."""

    DEFINITION = "definition"
    NORMATIVE = "normative"
    PROCEDURAL = "procedural"
    PENALTY = "penalty"
    RECITAL = "recital"
    SCOPE = "scope"
    GUIDANCE = "guidance"
    OTHER = "other"
