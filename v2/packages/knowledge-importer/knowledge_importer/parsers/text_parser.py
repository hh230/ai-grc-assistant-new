"""Plain-text extraction: the file already is its own reading-order text. Decoding
errors are replaced rather than raised so an unusual encoding degrades the output
instead of failing the whole document."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from knowledge_importer.parsers.base import ParsedText, ParseResult


@dataclass
class TextParser:
    name: str = "text"

    def parse(self, path: Path) -> ParseResult:
        parsed = ParsedText(text=path.read_text(encoding="utf-8", errors="replace"), page_count=None)
        return ParseResult.single(self.name, parsed)
