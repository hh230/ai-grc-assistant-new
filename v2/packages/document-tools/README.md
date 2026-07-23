# document-tools (V2)

Real, read-only GRC tools that **extract text from evidence documents** — the PDF/DOCX/Excel
readers of the Real Tools layer. They **consume the frozen `knowledge-importer` parsers** (pypdf →
pypdfium2 fallback, python-docx, openpyxl) rather than re-implementing extraction.

Three registered tools, one shared base (`DocumentReaderTool`):

| tool name | reads | wraps |
|---|---|---|
| `read_pdf` | `.pdf` | `knowledge_importer` `PdfParser` |
| `read_docx` | `.docx` | `knowledge_importer` `DocxParser` |
| `read_excel` | `.xlsx` | `knowledge_importer` `ExcelParser` |

Each satisfies the frozen `tool_registry.Tool` protocol, so a plan step routes to it by name via
`PlanStep.tool` (ADR 0048):

    Mission → ExecutionPort → RegistryExecutor → read_pdf → knowledge_importer PdfParser → text

## Contract

- **Input:** the step `instruction` is the document path, resolved **under a configured document
  root**. Traversal (`../`) and absolute paths outside the root are **refused** (CLAUDE.md §20,
  default deny) — the tool can never read arbitrary files.
- **Output:** a `ToolStepResult` (ADR 0049) — `output` is the extracted text, `source_ids` carries
  the document name as provenance, `warnings` note a fallback backend or truncation (`max_chars`).
- **Failure is safe:** a missing/oversized path, wrong type, or parse failure returns `ok=False`
  (the Mission fails safe, ADR 0042 §7) — never a raised exception across the tool boundary.

## Usage

```python
from document_tools import build_pdf_reader
from tool_registry import ToolRegistry

registry = ToolRegistry()
registry.register(build_pdf_reader(root="/srv/evidence/org_acme"))   # scoped to the tenant's docs

# a step then names it: PlanStep(instruction="policies/confidentiality.pdf", tool="read_pdf")
```

## Tests

`uv run pytest` builds **real** PDF/DOCX/XLSX files (reportlab / python-docx / openpyxl) under a
temp root and reads them back — extraction, provenance, wrong-type refusal, corrupt-file fail-safe,
path-traversal refusal, truncation, and a mission **E2E** through the real `RegistryExecutor`. No
network, no LLM. `ruff` + `mypy --strict` clean (knowledge-importer consumed as an untyped import).
