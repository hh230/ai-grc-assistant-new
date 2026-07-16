"""The contract every format-specific parser implements. `ParsingStage` (see
`../stages.py`) never contains format-specific logic itself — it only looks up a
`Parser` for a document's extension and calls `.parse()`. Adding support for a new
format (or, later, OCR for scanned PDFs) means adding one more class here and
registering it in `registry.py` — nothing else in the pipeline changes.

A `Parser` may try several *backends* in order (the PDF parser tries pypdf, then
pypdfium2 — see `pdf_backends/`). Every attempt is recorded on the returned
`ParseResult` (or, on total failure, on the raised `ParseError`), so the manifest can
report exactly which engine produced the text, whether a fallback was needed, and why
any attempt failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ParsedText:
    """The raw output of one extraction backend: text in reading order, plus a page
    count where the format has a meaningful notion of pages (`None` otherwise)."""

    text: str
    page_count: int | None


@dataclass(frozen=True)
class ParseAttempt:
    """A record of one backend being tried: which engine, whether it succeeded, and the
    failure reason if it didn't. The ordered list of these is the audit trail behind a
    parse — including the successful final attempt."""

    backend: str
    ok: bool
    error: str | None = None

    def to_json_dict(self) -> dict[str, object]:
        return {"backend": self.backend, "ok": self.ok, "error": self.error}


@dataclass(frozen=True)
class ParseResult:
    """A successful parse: the extracted text, its page count, the engine that produced
    it (`parser_used`), and the full ordered attempt trail."""

    text: str
    page_count: int | None
    parser_used: str
    attempts: tuple[ParseAttempt, ...]

    @property
    def fallback(self) -> bool:
        """True when the text came from a non-primary engine — i.e. at least one earlier
        backend was tried and failed before this one succeeded."""
        return any(not a.ok for a in self.attempts)

    @classmethod
    def single(cls, parser_name: str, parsed: ParsedText) -> ParseResult:
        """The result shape for a single-backend parser (docx, xlsx, txt, md): one
        successful attempt, no fallback possible."""
        return cls(
            text=parsed.text,
            page_count=parsed.page_count,
            parser_used=parser_name,
            attempts=(ParseAttempt(parser_name, ok=True),),
        )


class ParseError(Exception):
    """Raised when every backend a parser tried has failed. Carries the full attempt
    trail so `ParsingStage` can record each backend's failure reason on the manifest."""

    def __init__(self, attempts: tuple[ParseAttempt, ...]) -> None:
        self.attempts = attempts
        detail = "; ".join(f"{a.backend}: {a.error}" for a in attempts if not a.ok)
        super().__init__(detail or "all parser backends failed")


class Parser(Protocol):
    name: str

    def parse(self, path: Path) -> ParseResult: ...
