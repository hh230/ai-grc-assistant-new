from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from knowledge_importer.parsers.base import ParsedText, ParseError, ParseResult
from knowledge_importer.parsers.pdf_parser import PdfParser


@dataclass
class _OkBackend:
    name: str
    text: str = "hello"
    pages: int = 3

    def extract(self, path: Path) -> ParsedText:
        return ParsedText(text=self.text, page_count=self.pages)


@dataclass
class _FailBackend:
    name: str
    message: str = "boom"

    def extract(self, path: Path) -> ParsedText:
        raise ValueError(self.message)


def test_primary_backend_success_records_no_fallback(tmp_path: Path) -> None:
    parser = PdfParser(backends=[_OkBackend("pypdf"), _OkBackend("pypdfium2")])
    result = parser.parse(tmp_path / "x.pdf")
    assert result.parser_used == "pypdf"
    assert result.fallback is False
    assert [a.backend for a in result.attempts] == ["pypdf"]
    assert result.attempts[0].ok is True


def test_falls_back_to_second_backend_when_first_raises(tmp_path: Path) -> None:
    parser = PdfParser(backends=[_FailBackend("pypdf", "stream ended"), _OkBackend("pypdfium2", text="recovered", pages=60)])
    result = parser.parse(tmp_path / "x.pdf")
    assert result.parser_used == "pypdfium2"
    assert result.fallback is True
    assert result.text == "recovered"
    assert result.page_count == 60
    assert [(a.backend, a.ok) for a in result.attempts] == [("pypdf", False), ("pypdfium2", True)]
    assert "stream ended" in (result.attempts[0].error or "")


def test_all_backends_fail_raises_parse_error_with_full_trail(tmp_path: Path) -> None:
    parser = PdfParser(backends=[_FailBackend("pypdf", "e1"), _FailBackend("pypdfium2", "e2")])
    with pytest.raises(ParseError) as excinfo:
        parser.parse(tmp_path / "x.pdf")
    attempts = excinfo.value.attempts
    assert [a.backend for a in attempts] == ["pypdf", "pypdfium2"]
    assert all(not a.ok for a in attempts)
    assert "e1" in str(excinfo.value) and "e2" in str(excinfo.value)


def test_parse_result_single_has_one_successful_attempt() -> None:
    result = ParseResult.single("docx", ParsedText(text="body", page_count=None))
    assert result.parser_used == "docx"
    assert result.fallback is False
    assert len(result.attempts) == 1 and result.attempts[0].ok
