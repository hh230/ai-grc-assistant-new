from __future__ import annotations

from devteam_analysis import AnalyzedFailure, PNPMAnalyzer, RawFailure


def _analyze(logs: str, hint: str = "Run pnpm install") -> AnalyzedFailure | None:
    return PNPMAnalyzer().analyze(RawFailure(hint, logs))


def test_outdated_lockfile() -> None:
    analysis = _analyze("ERR_PNPM_OUTDATED_LOCKFILE  Cannot install with frozen-lockfile\n")
    assert analysis is not None
    assert analysis.category == "package_manager" and analysis.confidence == 1.0
    assert analysis.findings[0].code == "ERR_PNPM_OUTDATED_LOCKFILE"
    assert analysis.findings[0].file == "pnpm-lock.yaml"  # not source-located; the lockfile
    assert analysis.affected_files == ("pnpm-lock.yaml",)


def test_fetch_404_missing_package() -> None:
    analysis = _analyze("ERR_PNPM_FETCH_404  GET https://registry.npmjs.org/foo: Not Found - 404\n")
    assert analysis is not None
    assert analysis.findings[0].code == "ERR_PNPM_FETCH_404"
    assert "404" in analysis.findings[0].message


def test_multiple_pnpm_errors_are_deduped_by_code() -> None:
    analysis = _analyze(
        "ERR_PNPM_FETCH_404  a\nERR_PNPM_FETCH_404  a\nERR_PNPM_OUTDATED_LOCKFILE  b\n"
    )
    assert analysis is not None
    assert len(analysis.findings) == 2


def test_bare_command_failed_on_a_pnpm_step_is_recognized() -> None:
    analysis = _analyze("Command failed with exit code 1\n", hint="Run pnpm build")
    assert analysis is not None
    assert analysis.category == "package_manager"


def test_command_failed_on_a_non_pnpm_step_is_not_stolen() -> None:
    assert _analyze("Command failed with exit code 1\n", hint="Run something else") is None


def test_malformed_output_returns_none() -> None:
    assert _analyze("random noise, no pnpm error\n") is None
