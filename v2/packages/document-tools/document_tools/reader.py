"""`DocumentReaderTool` — a real, read-only GRC tool that extracts text from an evidence document.

It **consumes the frozen `knowledge-importer` parsers** (`Parser.parse(path) -> ParseResult`) rather
than re-implementing extraction — the PDF tool wraps `PdfParser` (pypdf → pypdfium2 fallback), DOCX
wraps `DocxParser`, Excel wraps `ExcelParser`. One base class parameterised by a parser + the
extensions it accepts + a registry name backs all three concrete tools (`tools.py`).

It satisfies the frozen `tool_registry.Tool` protocol, so it plugs into the execution path unchanged
and a plan step routes to it by name via `PlanStep.tool` (ADR 0048). The step's `instruction` is the
document path, resolved **under a configured document root** and rejected if it escapes it
(path-traversal safe — the tool never reads outside the tenant's document area). The extracted text
comes back as a `ToolStepResult` (ADR 0049): `output` is the text, `source_ids` carries the document
name as provenance, `warnings` note a fallback backend or truncation. Any failure (missing/oversized
path, unsupported type, parse failure) returns `ok=False` so the Mission fails safe — never a crash.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from knowledge_importer.parsers.base import ParseError, Parser
from pipeline_contracts import TenantContext
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, ToolSpec, ToolStepResult

from document_tools.errors import DocumentAccessError


class DocumentReaderTool:
    """A registered `Tool` that reads one document of an accepted type from under `root`."""

    def __init__(
        self,
        parser: Parser,
        extensions: Iterable[str],
        *,
        name: str,
        root: Path,
        version: int = 1,
        max_chars: int | None = None,
    ) -> None:
        self._parser = parser
        self._extensions = frozenset(ext.lower() for ext in extensions)
        self._root = Path(root)
        self._max_chars = max_chars
        exts = ", ".join(sorted(self._extensions))
        self._spec = ToolSpec(
            name=name,
            version=version,
            description=f"Extract text from a document ({exts}) under the tenant's document root.",
            side_effect=SideEffectProfile.READ_ONLY,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        raw = str(payload.get(PAYLOAD_INSTRUCTION, "")).strip()
        try:
            path = self._resolve(raw)
        except DocumentAccessError as exc:
            return _fail(str(exc))
        if path.suffix.lower() not in self._extensions:
            return _fail(f"unsupported document type {path.suffix!r} for {self._spec.name}")
        try:
            result = self._parser.parse(path)
        except ParseError as exc:
            return _fail(f"could not extract text from {path.name}: {exc}")
        backend = result.parser_used if result.fallback else ""
        return self._ok(path, result.text, fallback_backend=backend)

    def _resolve(self, raw: str) -> Path:
        """Resolve `raw` as a path **under** `root`, rejecting traversal and missing files. An
        absolute path outside the root, or a `../` escape, is refused — the tool cannot read
        arbitrary files (CLAUDE.md §20, default deny)."""
        if not raw:
            raise DocumentAccessError("no document path given")
        root = self._root.resolve()
        candidate = (root / raw).resolve()
        if candidate != root and root not in candidate.parents:
            raise DocumentAccessError(f"path {raw!r} escapes the document root")
        if not candidate.is_file():
            raise DocumentAccessError(f"document {raw!r} not found under the document root")
        return candidate

    def _ok(self, path: Path, text: str, *, fallback_backend: str) -> dict[str, object]:
        warnings: tuple[str, ...] = ()
        if fallback_backend:
            warnings += (f"primary parser failed; text produced by fallback {fallback_backend!r}",)
        if self._max_chars is not None and len(text) > self._max_chars:
            text = text[: self._max_chars]
            warnings += (f"output truncated to {self._max_chars} characters",)
        return ToolStepResult(
            ok=True, output=text, source_ids=(path.name,), warnings=warnings
        ).as_payload()


def _fail(reason: str) -> dict[str, object]:
    return ToolStepResult(ok=False, output="", warnings=(reason,)).as_payload()
