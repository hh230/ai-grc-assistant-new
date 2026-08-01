"""The path-resolver layer: turn an analyzer's logical paths into real repository paths so the
Developer reads real source and builds a diff ``git apply`` accepts. The final test is the whole
point of fix D — a member-relative finding resolves, the Developer's diff carries the REAL line and
the repo-relative path, and ``git apply --check`` accepts it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from devteam_agents import AnalysisProposer
from devteam_analysis import AnalyzedFailure, Finding
from devteam_contracts import platform_tenant
from devteam_protocol import AgentRequest, AgentRole
from devteam_runtime.path_resolver import resolve_paths


def _failure(*findings: Finding, category: str = "type_check") -> AnalyzedFailure:
    return AnalyzedFailure(
        category=category,
        summary="mypy failed",
        findings=findings,
        affected_files=tuple(f.file for f in findings),
    )


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_already_real_path_is_unchanged(tmp_path: Path) -> None:
    real = "packages/tools/grc_tools/x.py"
    _write(tmp_path, real, "x = 1\n")
    resolved = resolve_paths(_failure(Finding(real, 1, "a", "m")), tmp_path)
    assert resolved.findings[0].file == real


def test_member_relative_path_resolves_to_the_repo_path(tmp_path: Path) -> None:
    _write(tmp_path, "packages/tools/grc_tools/x.py", "x = 1\n")
    resolved = resolve_paths(_failure(Finding("grc_tools/x.py", 1, "a", "m")), tmp_path)
    assert resolved.findings[0].file == "packages/tools/grc_tools/x.py"  # logical -> real
    assert resolved.affected_files == ("packages/tools/grc_tools/x.py",)  # rebuilt from findings
    assert resolved.findings[0].line == 1 and resolved.findings[0].code == "a"  # rest untouched


def test_absent_path_is_left_unchanged(tmp_path: Path) -> None:
    resolved = resolve_paths(_failure(Finding("nowhere/x.py", 2, "a", "m")), tmp_path)
    assert resolved.findings[0].file == "nowhere/x.py"  # nothing to resolve to — left as-is


def test_ambiguous_path_is_left_unchanged(tmp_path: Path) -> None:
    _write(tmp_path, "a/grc_tools/x.py", "x = 1\n")
    _write(tmp_path, "b/grc_tools/x.py", "x = 1\n")
    resolved = resolve_paths(_failure(Finding("grc_tools/x.py", 1, "a", "m")), tmp_path)
    assert resolved.findings[0].file == "grc_tools/x.py"  # two matches -> ambiguous -> unchanged


def test_vendored_directories_are_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "node_modules/dep/grc_tools/x.py", "x = 1\n")  # must not be matched
    _write(tmp_path, "packages/tools/grc_tools/x.py", "x = 1\n")
    resolved = resolve_paths(_failure(Finding("grc_tools/x.py", 1, "a", "m")), tmp_path)
    assert resolved.findings[0].file == "packages/tools/grc_tools/x.py"  # node_modules ignored


def test_resolved_diff_is_real_and_applies_with_git_apply(tmp_path: Path) -> None:
    # The whole point of D: a member-relative finding -> the Developer reads the REAL line and
    # builds a diff that git apply accepts (not a placeholder against a path that does not exist).
    real = "packages/tools/grc_tools/probe.py"
    _write(tmp_path, real, "from __future__ import annotations\n\nvalue: str = 42\n")
    finding = Finding("grc_tools/probe.py", 3, "assignment", "types")  # member-relative

    resolved = resolve_paths(_failure(finding), tmp_path)
    proposer = AnalysisProposer(resolved, tmp_path)
    request = AgentRequest(
        role=AgentRole.DEVELOPER, intent="fix", tenant=platform_tenant(), inbox=None
    )
    diff = next(a.content for a in proposer(request) if a.kind == "diff")

    assert f"a/{real}" in diff and "# (see " not in diff  # repo-relative path, no placeholder
    assert "value: str = 42  # type: ignore[assignment]" in diff  # the REAL line, suppressed

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    (tmp_path / "fix.diff").write_text(diff, encoding="utf-8")
    check = subprocess.run(
        ["git", "apply", "--check", "fix.diff"], cwd=tmp_path, capture_output=True, text=True
    )
    assert check.returncode == 0, check.stderr  # the resolved diff actually applies
