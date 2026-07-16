"""DOCX text extraction. Walks the document body in document order (not
`document.paragraphs` alone) so paragraphs and tables come out interleaved exactly as
they appear in the source, rather than all paragraphs followed by all tables. DOCX has
no reliable notion of a fixed page — actual pagination depends on the renderer — so
`page_count` is always `None`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from knowledge_importer.parsers.base import ParsedText, ParseResult


@dataclass
class DocxParser:
    name: str = "docx"

    def parse(self, path: Path) -> ParseResult:
        document = Document(str(path))
        lines: list[str] = []
        for child in document.element.body.iterchildren():
            if child.tag == qn("w:p"):
                lines.append("".join(node.text or "" for node in child.iter(qn("w:t"))))
            elif child.tag == qn("w:tbl"):
                for row in child.iter(qn("w:tr")):
                    cells = ["".join(node.text or "" for node in cell.iter(qn("w:t"))) for cell in row.iter(qn("w:tc"))]
                    lines.append("\t".join(cells))
        return ParseResult.single(self.name, ParsedText(text="\n".join(lines), page_count=None))
