"""The path-safety and error contract of the reader base — the security-relevant behaviour
(CLAUDE.md §20, default deny): a reader can only read files *under* its configured root."""

from __future__ import annotations

from pathlib import Path

from document_tools import build_pdf_reader
from pipeline_contracts import TenantContext
from tool_registry import PAYLOAD_INSTRUCTION, ToolStepResult


def _read(tool, tenant: TenantContext, path: str) -> ToolStepResult:
    return ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: path}, tenant))


def test_traversal_outside_the_root_is_refused(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_pdf_reader(doc_root), tenant, "../../../../etc/passwd")
    assert result.ok is False
    assert "escapes the document root" in result.warnings[0]


def test_absolute_path_outside_root_is_refused(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_pdf_reader(doc_root), tenant, "/etc/hosts")
    assert result.ok is False
    assert "escapes the document root" in result.warnings[0]


def test_a_missing_file_fails_safe(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_pdf_reader(doc_root), tenant, "nope.pdf")
    assert result.ok is False
    assert "not found" in result.warnings[0]


def test_an_empty_instruction_fails_safe(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_pdf_reader(doc_root), tenant, "")
    assert result.ok is False
    assert "no document path" in result.warnings[0]
