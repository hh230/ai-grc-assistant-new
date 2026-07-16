"""PDF text extraction as an ordered chain of backends (see `pdf_backends/`). Tries each
engine in turn: the first that succeeds wins, and its result records the full attempt
trail (so the manifest can show whether a fallback was needed and why the primary
failed). If every backend fails, raises `ParseError` carrying that same trail.

The chain is injected, not hardcoded, so tests and future callers can supply their own
ordering or add an OCR backend without touching this class."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from knowledge_importer.parsers.base import ParseAttempt, ParseError, ParseResult
from knowledge_importer.parsers.pdf_backends import DEFAULT_PDF_BACKENDS, PdfBackend


@dataclass
class PdfParser:
    name: str = "pdf"
    backends: Sequence[PdfBackend] = field(default_factory=lambda: DEFAULT_PDF_BACKENDS)

    def parse(self, path: Path) -> ParseResult:
        attempts: list[ParseAttempt] = []
        for backend in self.backends:
            try:
                parsed = backend.extract(path)
            except Exception as exc:  # noqa: BLE001 - any backend failure falls through to the next
                attempts.append(ParseAttempt(backend.name, ok=False, error=f"{type(exc).__name__}: {exc}"))
                continue
            attempts.append(ParseAttempt(backend.name, ok=True))
            return ParseResult(
                text=parsed.text,
                page_count=parsed.page_count,
                parser_used=backend.name,
                attempts=tuple(attempts),
            )
        raise ParseError(tuple(attempts))
