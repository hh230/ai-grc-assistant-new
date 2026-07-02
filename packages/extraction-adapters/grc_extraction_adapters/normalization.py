"""A rule-based normalizer (implements ``NormalizerPort``).

Collapses runs of whitespace, drops blocks that become empty, and language-tags the document —
preserving block order and page positions for downstream segmentation. No NLP library or model.
"""
from __future__ import annotations

from dataclasses import replace

from grc_extraction import NormalizedDocument, NormalizerPort, ParsedDocument


class WhitespaceNormalizer(NormalizerPort):
    """Cleans parsed content by collapsing whitespace while preserving structure."""

    def __init__(self, *, name: str = "whitespace", version: str = "1.0.0") -> None:
        self._name = name
        self._version = version

    async def normalize(
        self, document: ParsedDocument, *, language: str | None = None
    ) -> NormalizedDocument:
        blocks = tuple(
            replace(block, text=collapsed)
            for block in document.blocks
            if (collapsed := " ".join(block.text.split()))
        )
        return NormalizedDocument(
            blocks=blocks,
            language=language or document.language,
            normalizer_name=self._name,
            normalizer_version=self._version,
        )
