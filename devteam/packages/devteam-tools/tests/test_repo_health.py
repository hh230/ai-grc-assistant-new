from __future__ import annotations

from pathlib import Path

from devteam_tools import CHECK_REPO_HEALTH, CheckRepoHealthTool
from pipeline_contracts import TenantContext
from tool_registry.result import ToolStepResult
from tool_registry.spec import SideEffectProfile


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="platform", principal_id="test")


def test_spec_is_readonly_and_named() -> None:
    tool = CheckRepoHealthTool(repo_root=".")
    assert tool.spec.name == CHECK_REPO_HEALTH
    assert tool.spec.side_effect is SideEffectProfile.READ_ONLY
    assert not tool.spec.is_consequential


def test_healthy_on_a_real_git_repo(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# constitution\n")
    result = ToolStepResult.from_payload(CheckRepoHealthTool(tmp_path).invoke({}, _tenant()))
    assert result.ok is True
    assert "git=True" in result.output
    assert "claude_md=True" in result.output


def test_unhealthy_when_not_a_git_repo(tmp_path: Path) -> None:
    result = ToolStepResult.from_payload(CheckRepoHealthTool(tmp_path).invoke({}, _tenant()))
    assert result.ok is False
    assert result.warnings
