"""Rasheed V2 Document Tools — real, read-only GRC tools that extract text from evidence documents.

Three registered `Tool`s — `read_pdf`, `read_docx`, `read_excel` — that **consume the frozen
`knowledge-importer` parsers** (no re-implementation of extraction). Each reads one document from
under a configured, path-traversal-safe document root and returns its text as a `ToolStepResult`.
Runtime deps: the pure `tool-registry` + `pipeline-contracts` + the existing `knowledge-importer`;
no LLM, no Core change.
"""

from document_tools.errors import DocumentAccessError, DocumentToolError
from document_tools.reader import DocumentReaderTool
from document_tools.tools import (
    READ_DOCX_TOOL,
    READ_EXCEL_TOOL,
    READ_PDF_TOOL,
    build_docx_reader,
    build_excel_reader,
    build_pdf_reader,
)

__all__ = [
    "DocumentReaderTool",
    "build_pdf_reader",
    "build_docx_reader",
    "build_excel_reader",
    "READ_PDF_TOOL",
    "READ_DOCX_TOOL",
    "READ_EXCEL_TOOL",
    "DocumentToolError",
    "DocumentAccessError",
]
