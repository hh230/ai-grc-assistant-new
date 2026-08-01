from __future__ import annotations

from pathlib import Path

from devteam_analysis import AnalyzedFailure, RawFailure, RuffAnalyzer


def _analyze(logs: str) -> AnalyzedFailure | None:
    return RuffAnalyzer().analyze(RawFailure("Run uv run ruff check .", logs))


def _fixture(tool: str, name: str) -> str:
    return (Path(__file__).parent / "fixtures" / "github" / tool / name).read_text(encoding="utf-8")


def test_parses_f401_unused_import_with_a_github_timestamp() -> None:
    analysis = _analyze(
        "2026-07-09T18:49:31.2504022Z packages/core/foo.py:18:5: F401 `os` imported but unused\n"
    )
    assert analysis is not None
    assert analysis.category == "lint" and analysis.confidence == 1.0
    finding = analysis.findings[0]
    assert (finding.file, finding.line, finding.code) == ("packages/core/foo.py", 18, "F401")
    assert "imported but unused" in finding.message


def test_parses_e402_import_order() -> None:
    analysis = _analyze("packages/app/main.py:44:1: E402 Module level import not at top of file\n")
    assert analysis is not None
    assert analysis.findings[0].code == "E402"
    assert analysis.findings[0].message == "Module level import not at top of file"


def test_multiple_files_are_all_affected() -> None:
    analysis = _analyze(
        "packages/core/foo.py:18:5: F401 `os` imported but unused\n"
        "packages/app/main.py:44:1: E402 Module level import not at top of file\n"
    )
    assert analysis is not None
    assert len(analysis.findings) == 2
    assert analysis.affected_files == ("packages/core/foo.py", "packages/app/main.py")
    assert "2 lint violation" in analysis.summary


def test_ignores_non_violation_lines() -> None:
    analysis = _analyze(
        "Checking 42 files...\n"
        "packages/core/foo.py:18:5: F401 `os` imported but unused\n"
        "Found 1 error.\n"
        "[*] 1 fixable with the `--fix` option.\n"
    )
    assert analysis is not None
    assert len(analysis.findings) == 1  # only the violation line


def test_duplicate_violations_are_removed() -> None:
    analysis = _analyze(
        "packages/core/foo.py:18:5: F401 `os` imported but unused\n"
        "packages/core/foo.py:18:5: F401 `os` imported but unused\n"
    )
    assert analysis is not None
    assert len(analysis.findings) == 1


def test_parses_the_full_default_format_from_a_real_log() -> None:
    # Regression fixture: the REAL ruff full-format output (CODE line + `--> file:line:col`) that
    # once produced zero findings. Locks the parser against reintroducing that bug (ADR 0061).
    analysis = _analyze(_fixture("ruff", "full_format.log"))
    assert analysis is not None
    assert analysis.category == "lint" and analysis.confidence == 1.0
    codes = {finding.code for finding in analysis.findings}
    assert {"E501", "UP035", "I001"} <= codes  # the [*] fixable marker is dropped from UP035
    e501 = next(finding for finding in analysis.findings if finding.code == "E501")
    assert e501.file == "apps/api/openapi/generate.py" and e501.line == 28
    assert "Line too long" in e501.message


def test_returns_none_without_ruff_output() -> None:
    assert _analyze("no ruff violations here\n") is None
