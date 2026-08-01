"""The three concrete document reader tools, each wrapping a `knowledge-importer` parser.

`read_pdf` / `read_docx` / `read_excel` are distinct registered tools (distinct names, distinct
accepted extensions), all built on the one `DocumentReaderTool` base. A plan step names the one it
needs via `PlanStep.tool` (ADR 0048); the composition root registers each under its name.
"""

from __future__ import annotations

from pathlib import Path

from knowledge_importer.parsers.docx_parser import DocxParser
from knowledge_importer.parsers.excel_parser import ExcelParser
from knowledge_importer.parsers.pdf_parser import PdfParser

from document_tools.reader import DocumentReaderTool

READ_PDF_TOOL = "read_pdf"
READ_DOCX_TOOL = "read_docx"
READ_EXCEL_TOOL = "read_excel"


def build_pdf_reader(root: Path | str, *, max_chars: int | None = None) -> DocumentReaderTool:
    return DocumentReaderTool(
        PdfParser(), (".pdf",), name=READ_PDF_TOOL, root=Path(root), max_chars=max_chars
    )


def build_docx_reader(root: Path | str, *, max_chars: int | None = None) -> DocumentReaderTool:
    return DocumentReaderTool(
        DocxParser(), (".docx",), name=READ_DOCX_TOOL, root=Path(root), max_chars=max_chars
    )


def build_excel_reader(root: Path | str, *, max_chars: int | None = None) -> DocumentReaderTool:
    return DocumentReaderTool(
        ExcelParser(), (".xlsx",), name=READ_EXCEL_TOOL, root=Path(root), max_chars=max_chars
    )
