from __future__ import annotations

from devteam_analysis import AnalyzedFailure, PytestAnalyzer, RawFailure


def _analyze(logs: str) -> AnalyzedFailure | None:
    return PytestAnalyzer().analyze(RawFailure("Run pytest", logs))


def test_assertion_error() -> None:
    analysis = _analyze(
        "FAILED tests/test_user.py::test_create_user - AssertionError: assert 1 == 2\n"
    )
    assert analysis is not None
    assert analysis.category == "tests"
    finding = analysis.findings[0]
    assert finding.file == "tests/test_user.py"
    assert finding.code == "AssertionError"
    assert "assert 1 == 2" in finding.message


def test_type_error() -> None:
    analysis = _analyze("FAILED tests/test_api.py::test_call - TypeError: expected str, got int\n")
    assert analysis is not None
    assert analysis.findings[0].code == "TypeError"


def test_value_error() -> None:
    analysis = _analyze("FAILED tests/test_x.py::test_parse - ValueError: invalid literal\n")
    assert analysis is not None
    assert analysis.findings[0].code == "ValueError"


def test_multiple_failing_tests() -> None:
    analysis = _analyze(
        "FAILED tests/test_user.py::test_create_user - AssertionError: assert 1 == 2\n"
        "FAILED tests/test_api.py::test_call - TypeError: x\n"
    )
    assert analysis is not None
    assert len(analysis.findings) == 2
    assert analysis.affected_files == ("tests/test_user.py", "tests/test_api.py")
    assert "2 failing test" in analysis.summary


def test_failed_without_a_detail_is_still_a_finding() -> None:
    analysis = _analyze("FAILED tests/test_user.py::test_create_user\n")
    assert analysis is not None
    assert analysis.findings[0].code == ""
    assert analysis.findings[0].message == "test_create_user"


def test_returns_none_without_failures() -> None:
    assert _analyze("all tests passed\n") is None
