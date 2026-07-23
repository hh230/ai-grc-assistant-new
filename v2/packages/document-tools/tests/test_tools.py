"""The three reader tools against real documents: they extract text, carry provenance, are
read-only registry tools, and refuse the wrong type — all via the frozen contract."""

from __future__ import annotations

from pathlib import Path

from document_tools import (
    READ_DOCX_TOOL,
    READ_EXCEL_TOOL,
    READ_PDF_TOOL,
    build_docx_reader,
    build_excel_reader,
    build_pdf_reader,
)
from pipeline_contracts import TenantContext
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, Tool, ToolStepResult


def _read(tool, tenant: TenantContext, path: str) -> ToolStepResult:
    return ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: path}, tenant))


def test_all_three_are_read_only_registry_tools(doc_root: Path) -> None:
    for build, name in (
        (build_pdf_reader, READ_PDF_TOOL),
        (build_docx_reader, READ_DOCX_TOOL),
        (build_excel_reader, READ_EXCEL_TOOL),
    ):
        tool = build(doc_root)
        assert isinstance(tool, Tool)
        assert tool.spec.name == name
        assert tool.spec.side_effect is SideEffectProfile.READ_ONLY


def test_pdf_reader_extracts_text(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_pdf_reader(doc_root), tenant, "confidentiality.pdf")
    assert result.ok
    assert "Confidentiality Policy" in result.output
    assert "Access control requirements" in result.output   # page two survived
    assert result.source_ids == ("confidentiality.pdf",)     # provenance


def test_docx_reader_reads_a_nested_path(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_docx_reader(doc_root), tenant, "policies/access-control.docx")
    assert result.ok
    assert "This policy governs access control." in result.output
    assert result.source_ids == ("access-control.docx",)


def test_excel_reader_extracts_cell_text(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_excel_reader(doc_root), tenant, "controls.xlsx")
    assert result.ok
    assert "AC-1" in result.output and "Access Control Policy" in result.output


def test_each_reader_refuses_the_wrong_type(doc_root: Path, tenant: TenantContext) -> None:
    # the PDF reader must not accept a .docx, etc. — a fail-safe ok=False, not a crash.
    result = _read(build_pdf_reader(doc_root), tenant, "policies/access-control.docx")
    assert result.ok is False
    assert "unsupported document type" in result.warnings[0]


def test_a_corrupt_pdf_fails_safe(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_pdf_reader(doc_root), tenant, "broken.pdf")
    assert result.ok is False
    assert result.output == ""
    assert result.warnings


def test_max_chars_truncates_with_a_warning(doc_root: Path, tenant: TenantContext) -> None:
    result = _read(build_pdf_reader(doc_root, max_chars=5), tenant, "confidentiality.pdf")
    assert result.ok
    assert len(result.output) == 5
    assert any("truncated" in w for w in result.warnings)
