from __future__ import annotations

from pathlib import Path

from devteam_analysis import (
    AnalyzedFailure,
    ESLintAnalyzer,
    FailureAnalyzer,
    MypyAnalyzer,
    PNPMAnalyzer,
    PytestAnalyzer,
    RawFailure,
    RuffAnalyzer,
    analyze_failure,
)

_LOG = (
    "2024-01-01T00:00:00Z Run uv run mypy .\n"
    "2024-01-01T00:00:01Z src/foo.py:2: error: Missing return type  [no-untyped-def]\n"
    '2024-01-01T00:00:02Z src/bar.py:5: error: Name "x" is not defined  [name-defined]\n'
    "2024-01-01T00:00:03Z Found 2 errors in 2 files\n"
)


class _NeverMatches:
    """A FailureAnalyzer that recognizes nothing — proves the dispatcher moves on."""

    def analyze(self, failure: RawFailure) -> AnalyzedFailure | None:
        return None


def _fixture(tool: str, name: str) -> str:
    return (Path(__file__).parent / "fixtures" / "github" / tool / name).read_text(encoding="utf-8")


def test_mypy_analyzer_returns_none_without_mypy_errors() -> None:
    assert MypyAnalyzer().analyze(RawFailure("Run pytest", "no type errors here\n")) is None


def test_mypy_analyzer_parses_a_module_level_error_from_a_real_log() -> None:
    # Regression fixture: the REAL GitHub log where a module-level error (no line number) once
    # produced zero findings. Locks the parser against reintroducing that bug (ADR 0061).
    analysis = MypyAnalyzer().analyze(
        RawFailure("Run uv run mypy .", _fixture("mypy", "duplicate_module.log"))
    )
    assert analysis is not None
    assert len(analysis.findings) == 1  # the note lines are ignored; only the error is a finding
    finding = analysis.findings[0]
    assert finding.file == "packages/domain/tests/knowledge/test_value_objects.py"
    assert finding.line == 0  # module-level: no line number
    assert finding.code == ""  # this diagnostic carries no error code
    assert "Duplicate module" in finding.message
    assert analysis.affected_symbols == ("test_value_objects",)  # quoted path filtered out


def test_mypy_analyzer_produces_diagnostics_only() -> None:
    analysis = MypyAnalyzer().analyze(RawFailure("Run uv run mypy .", _LOG))
    assert analysis is not None
    assert analysis.category == "type_check"
    assert analysis.confidence == 1.0
    assert [(f.file, f.line, f.code) for f in analysis.findings] == [
        ("src/foo.py", 2, "no-untyped-def"),
        ("src/bar.py", 5, "name-defined"),
    ]
    assert analysis.affected_files == ("src/foo.py", "src/bar.py")
    assert analysis.affected_symbols == ("x",)  # extracted from the quoted diagnostic
    assert "mypy" not in analysis.summary.lower()  # tool-agnostic
    assert not hasattr(analysis, "edits")  # diagnostic-only: analyzers never engineer


def test_analyze_failure_dispatches_to_the_first_matching_analyzer() -> None:
    analysis = analyze_failure(RawFailure("mypy", _LOG), [_NeverMatches(), MypyAnalyzer()])
    assert analysis is not None and analysis.category == "type_check"


def test_analyze_failure_is_none_when_no_analyzer_matches() -> None:
    assert analyze_failure(RawFailure("mypy", "irrelevant"), [_NeverMatches()]) is None


def test_dispatch_routes_each_tool_to_its_own_analyzer() -> None:
    analyzers: list[FailureAnalyzer] = [
        MypyAnalyzer(),
        RuffAnalyzer(),
        ESLintAnalyzer(),
        PytestAnalyzer(),
        PNPMAnalyzer(),
    ]
    cases = {
        "type_check": "app/x.py:1: error: boom  [misc]\n",
        "tests": "FAILED tests/t.py::test_a - AssertionError: nope\n",
        "package_manager": "ERR_PNPM_OUTDATED_LOCKFILE  stale\n",
    }
    # ruff needs its own case (category "lint" too, but a distinct format from eslint)
    for expected, logs in cases.items():
        result = analyze_failure(RawFailure("step", logs), analyzers)
        assert result is not None and result.category == expected

    ruff = analyze_failure(RawFailure("Run ruff", "app/x.py:1:1: F401 unused\n"), analyzers)
    assert ruff is not None and ruff.category == "lint" and ruff.findings[0].code == "F401"

    eslint_log = (
        "src/a.ts\n  1:1  error  Unexpected any  no-any\n✖ 1 problem (1 error, 0 warnings)\n"
    )
    eslint = analyze_failure(RawFailure("Run pnpm lint", eslint_log), analyzers)
    assert eslint is not None and eslint.category == "lint"
    assert eslint.findings[0].file == "src/a.ts"
