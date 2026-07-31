from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from devteam_ci import test_runner as tr
from devteam_ci.test_runner import (
    PackageResult,
    classify,
    discover_packages,
    format_report,
    run_package,
)


def _make_pkg(base: Path, name: str, *, with_tests: bool = True) -> Path:
    pkg = base / name
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    if with_tests:
        (pkg / "tests").mkdir()
    return pkg


def test_discover_finds_only_packages_with_pyproject_and_tests(tmp_path: Path) -> None:
    root = tmp_path / "v2" / "packages"
    a = _make_pkg(root, "aaa")
    _make_pkg(root, "bbb", with_tests=False)  # no tests/ -> skipped
    c = _make_pkg(root, "ccc")
    (root / "not-a-pkg").mkdir()  # no pyproject -> skipped
    assert discover_packages(tmp_path, ["v2/packages"]) == [a, c]


def test_discover_skips_missing_roots(tmp_path: Path) -> None:
    assert discover_packages(tmp_path, ["does/not/exist"]) == []


def test_result_ok_folds_pass_and_no_tests() -> None:
    assert PackageResult("x", 0, "").ok is True
    assert PackageResult("x", 5, "").ok is True  # no tests collected is not a failure
    assert PackageResult("x", 1, "").ok is False  # real failures


def test_classify_returns_last_nonempty_line() -> None:
    assert classify(0, "collecting...\n\n3 passed in 0.1s\n") == "3 passed in 0.1s"
    assert classify(5, "") == "no tests collected"
    assert classify(2, "") == "exit 2 (no output)"


def test_run_package_turns_a_timeout_into_a_failed_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="uv", timeout=1)

    monkeypatch.setattr(subprocess, "run", boom)
    result = run_package(tmp_path, timeout=1.0)
    assert result.ok is False
    assert "TIMEOUT" in result.summary


def test_format_report_lists_totals_and_failures() -> None:
    results = [PackageResult("aaa", 0, "3 passed"), PackageResult("bbb", 1, "1 failed")]
    report = format_report(results)
    assert "[PASS] aaa" in report
    assert "[FAIL] bbb" in report
    assert "1 ok, 1 failed" in report
    assert "failed: bbb" in report


def test_module_exposes_default_roots() -> None:
    assert "v2/packages" in tr.DEFAULT_ROOTS
    assert "v3/packages" in tr.DEFAULT_ROOTS
