"""Markdown extraction: kept as its own parser (rather than aliased to `TextParser`) so
a future version can strip formatting or extract structure without touching the plain
`.txt` path. For now it reads the raw source unchanged, same as `TextParser`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from knowledge_importer.parsers.base import ParsedText, ParseResult


@dataclass
class MarkdownParser:
    name: str = "markdown"

    def parse(self, path: Path) -> ParseResult:
        parsed = ParsedText(text=path.read_text(encoding="utf-8", errors="replace"), page_count=None)
        return ParseResult.single(self.name, parsed)
