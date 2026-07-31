from __future__ import annotations

import subprocess
from pathlib import Path

from devteam_agents import AnalysisProposer, DeveloperAgent
from devteam_analysis import AnalyzedFailure, Finding
from devteam_protocol import AgentRequest, AgentRole, AgentVerdict
from pipeline_contracts import TenantContext


def _request() -> AgentRequest:
    return AgentRequest(
        role=AgentRole.DEVELOPER,
        intent="fix the failing step",
        tenant=TenantContext(tenant_id="platform", principal_id="dev"),
    )


def _type_check(file: str = "src/x.py") -> AnalyzedFailure:
    return AnalyzedFailure(
        category="type_check",
        summary="Type checking reported 1 error(s).",
        findings=(Finding(file, 2, "no-untyped-def", "Missing return type"),),
        affected_files=(file,),
        confidence=1.0,
    )


def test_developer_engineers_a_diff_from_diagnostics_reading_the_real_file(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def f():\n    return None\n")  # line 2
    artifacts = AnalysisProposer(_type_check(), tmp_path)(_request())
    assert [a.kind for a in artifacts] == ["diagnosis", "reasoning", "plan", "diff"]
    diff = next(a for a in artifacts if a.kind == "diff").content
    assert "-    return None" in diff  # the Developer read the real source line
    assert "+    return None  # type: ignore[no-untyped-def]" in diff  # its fix decision
    # generic: the Developer's own artifacts never name the tool
    assert "mypy" not in " ".join(a.content for a in artifacts).lower()


def test_developer_declines_when_the_file_is_absent(tmp_path: Path) -> None:
    # No real source to read → no real diff can be built. The Developer declines (diagnosis + plan
    # only) rather than emit a placeholder diff that git apply would reject.
    kinds = [a.kind for a in AnalysisProposer(_type_check("gone/y.py"), tmp_path)(_request())]
    assert kinds == ["diagnosis", "reasoning", "plan"]  # no diff


def test_developer_diff_is_a_standard_unified_diff_that_plain_git_apply_accepts(
    tmp_path: Path,
) -> None:
    # The root-cause fix: a real unified diff with context, applied by PLAIN `git apply` — no
    # --unidiff-zero, no other options. Uses a mid-file target so there is context on both sides.
    src = tmp_path / "src" / "x.py"
    src.parent.mkdir(parents=True)
    src.write_text("def f():\n    x = 1\n    return None\n    z = 2\n")  # target line 3
    finding = Finding("src/x.py", 3, "no-untyped-def", "Missing return type")
    analysis = AnalyzedFailure(category="type_check", summary="1 error", findings=(finding,))
    diff = next(a for a in AnalysisProposer(analysis, tmp_path)(_request()) if a.kind == "diff")

    assert "@@ -1,4 +1,4 @@" in diff.content  # a real hunk header with context, not @@ -3,1 +3,1 @@
    assert " def f():" in diff.content  # a context line, space-prefixed (present on both sides)
    assert "-    return None" in diff.content  # the removed line
    assert "+    return None  # type: ignore[no-untyped-def]" in diff.content  # the added line

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    (tmp_path / "fix.diff").write_text(diff.content, encoding="utf-8")
    check = subprocess.run(
        ["git", "apply", "--check", "fix.diff"], cwd=tmp_path, capture_output=True, text=True
    )
    assert check.returncode == 0, check.stderr  # plain git apply accepts it


def test_developer_has_no_deterministic_fix_for_an_unhandled_category(tmp_path: Path) -> None:
    # No strategy for 'tests' yet — the Developer diagnoses and plans, but proposes no diff (an LLM
    # Developer would reason a real fix). Engineering, not assembly: it declines rather than guess.
    analysis = AnalyzedFailure(
        category="tests",
        summary="1 test failed.",
        findings=(Finding("tests/test_x.py", 9, "", "assert 1 == 2"),),
    )
    kinds = [a.kind for a in AnalysisProposer(analysis, tmp_path)(_request())]
    assert kinds == ["diagnosis", "reasoning", "plan"]


def test_developer_declines_a_diff_for_a_module_level_error(tmp_path: Path) -> None:
    # A module-level type error (line 0) is not line-suppressible — the Developer diagnoses and
    # plans but declines a diff (an LLM would propose the structural fix: __init__.py/--exclude).
    analysis = AnalyzedFailure(
        category="type_check",
        summary="Type checking reported 1 error(s).",
        findings=(Finding("pkg/a/dup.py", 0, "", 'Duplicate module named "dup"'),),
        affected_files=("pkg/a/dup.py",),
    )
    kinds = [a.kind for a in AnalysisProposer(analysis, tmp_path)(_request())]
    assert kinds == ["diagnosis", "reasoning", "plan"]  # no diff — declined, not guessed


def test_developer_proceeds_with_a_diff_and_abstains_without(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("def f():\n    return None\n")
    with_diff = DeveloperAgent(AnalysisProposer(_type_check(), tmp_path)).handle(_request())
    assert with_diff.decision is not None and with_diff.decision.verdict is AgentVerdict.PROCEED
    assert "```diff" in with_diff.output

    unhandled = AnalyzedFailure(
        category="tests", summary="x", findings=(Finding("t.py", 1, "", "boom"),)
    )
    without = DeveloperAgent(AnalysisProposer(unhandled, tmp_path)).handle(_request())
    assert without.decision is not None and without.decision.verdict is AgentVerdict.ABSTAIN
