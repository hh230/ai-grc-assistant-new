"""XLSX text extraction. Reading order is sheet order, then row order, then column
order within a row; each row's cells are joined with a tab so column structure survives
in the flattened text. A sheet is the closest XLSX equivalent of a "page", so sheets are
separated with a form-feed (`\\f`) and `page_count` is the sheet count."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl

from knowledge_importer.parsers.base import ParsedText, ParseResult


@dataclass
class ExcelParser:
    name: str = "xlsx"

    def parse(self, path: Path) -> ParseResult:
        workbook = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
        try:
            sheet_texts = []
            for sheet in workbook.worksheets:
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    cells = ["" if value is None else str(value) for value in row]
                    rows.append("\t".join(cells))
                sheet_texts.append("\n".join(rows))
        finally:
            workbook.close()
        return ParseResult.single(self.name, ParsedText(text="\f".join(sheet_texts), page_count=len(sheet_texts)))
