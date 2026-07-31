"""``check_repo_health`` — the dev team's first, trivial, read-only Tool (ADR 0061, Phase 0).

It exists to prove the seam end to end: a Dev Mission plans a step that routes here, the
``DevToolExecutor`` resolves it via the Tool Registry and invokes it with the platform tenant, and
the result flows back into the mission record and the audit trail. It performs a read-only check of
a repository working tree (existence, ``.git``, ``CLAUDE.md``, entry count) and returns a
``ToolStepResult``. It writes nothing — it is ``SideEffectProfile.READ_ONLY``.
"""

from __future__ import annotations

from pathlib import Path

from pipeline_contracts import TenantContext
from tool_registry.result import PAYLOAD_INSTRUCTION, ToolStepResult
from tool_registry.spec import SideEffectProfile, ToolSpec

from devteam_tools.names import CHECK_REPO_HEALTH


class CheckRepoHealthTool:
    """A read-only ``Tool`` reporting basic facts about a repo working tree. Construct it with the
    repository root it should inspect; ``invoke`` returns a ``ToolStepResult`` payload the executor
    maps to a ``StepResult``. Never writes — safe to run autonomously, no human gate (ADR 0061)."""

    def __init__(self, repo_root: Path | str) -> None:
        self._repo_root = Path(repo_root)

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=CHECK_REPO_HEALTH,
            version=1,
            description="Read-only health check of a repository working tree.",
            side_effect=SideEffectProfile.READ_ONLY,
        )

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        # The instruction is carried for symmetry with every tool; this leaf tool does not need it.
        _ = payload.get(PAYLOAD_INSTRUCTION, "")
        root = self._repo_root
        exists = root.is_dir()
        is_git = (root / ".git").is_dir()
        has_claude_md = (root / "CLAUDE.md").is_file()
        entry_count = sum(1 for _ in root.iterdir()) if exists else 0

        healthy = exists and is_git
        warnings: tuple[str, ...] = ()
        if not exists:
            warnings = (f"repository root does not exist: {root}",)
        elif not is_git:
            warnings = (f"not a git repository (no .git): {root}",)

        summary = (
            f"repo={root} exists={exists} git={is_git} "
            f"claude_md={has_claude_md} entries={entry_count}"
        )
        return ToolStepResult(ok=healthy, output=summary, warnings=warnings).as_payload()
