"""Maps a file extension to the `Parser` that handles it. This is the single place
`ParsingStage` consults to pick a parser — adding OCR support for scanned PDFs, or a new
format, means adding an entry here (and its own parser module), never touching
`ParsingStage` itself."""

from __future__ import annotations

from knowledge_importer.parsers.base import Parser
from knowledge_importer.parsers.docx_parser import DocxParser
from knowledge_importer.parsers.excel_parser import ExcelParser
from knowledge_importer.parsers.markdown_parser import MarkdownParser
from knowledge_importer.parsers.pdf_parser import PdfParser
from knowledge_importer.parsers.text_parser import TextParser

_PARSERS: dict[str, Parser] = {
    ".pdf": PdfParser(),
    ".docx": DocxParser(),
    ".xlsx": ExcelParser(),
    ".txt": TextParser(),
    ".md": MarkdownParser(),
}


def get_parser(extension: str) -> Parser | None:
    return _PARSERS.get(extension.lower())
