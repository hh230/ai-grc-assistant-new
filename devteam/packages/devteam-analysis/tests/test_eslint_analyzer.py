from __future__ import annotations

from devteam_analysis import AnalyzedFailure, ESLintAnalyzer, RawFailure


def _analyze(logs: str) -> AnalyzedFailure | None:
    return ESLintAnalyzer().analyze(RawFailure("Run pnpm lint", logs))


def test_single_file_error() -> None:
    analysis = _analyze(
        "src/app.ts\n"
        "  14:7  error  Unexpected any  @typescript-eslint/no-explicit-any\n"
        "\n"
        "✖ 1 problem (1 error, 0 warnings)\n"
    )
    assert analysis is not None
    assert analysis.category == "lint"
    finding = analysis.findings[0]
    assert (finding.file, finding.line, finding.code) == (
        "src/app.ts",
        14,
        "@typescript-eslint/no-explicit-any",
    )
    assert finding.message == "Unexpected any"
    assert analysis.affected_files == ("src/app.ts",)


def test_multiple_files() -> None:
    analysis = _analyze(
        "src/app.ts\n"
        "  14:7  error  Unexpected any  @typescript-eslint/no-explicit-any\n"
        "src/util.ts\n"
        "  3:1  error  Missing return type  @typescript-eslint/explicit-function-return-type\n"
        "✖ 2 problems (2 errors, 0 warnings)\n"
    )
    assert analysis is not None
    assert len(analysis.findings) == 2
    assert analysis.affected_files == ("src/app.ts", "src/util.ts")


def test_warnings_are_ignored_but_errors_are_findings() -> None:
    analysis = _analyze(
        "src/app.ts\n"
        "  10:1  warning  Unexpected console statement  no-console\n"
        "  14:7  error  Unexpected any  @typescript-eslint/no-explicit-any\n"
        "✖ 2 problems (1 error, 1 warning)\n"
    )
    assert analysis is not None
    assert len(analysis.findings) == 1  # the warning is not a finding
    assert analysis.findings[0].line == 14
    assert "1 error" in analysis.summary


def test_malformed_output_returns_none() -> None:
    assert _analyze("some unrelated noise\nnot eslint at all\n") is None
