"""path_resolver.py — turn an analyzer's logical file paths into real repository paths (ADR 0061).

A separate layer between the (diagnostic-only) analysis and the Developer. Some tools report paths
that are not repository-relative: a per-member mypy run (``mypy-workspace.sh``) reports
``grc_tools/x.py`` for a file that actually lives at ``packages/tools/grc_tools/x.py``. The
Developer must read real source to build a diff that ``git apply`` accepts, and it must stay
tool-agnostic — so turning a logical path into a real one is THIS layer's job, before the Developer.

Resolution is by repository search, not tool knowledge: a logical path resolves to the unique repo
file whose repo-relative path ends with it (so member-/package-/workspace-relative all resolve). An
already-real path is returned unchanged; an absent or ambiguous one is left as-is for a human/LLM.
"""

from __future__ import annotations

import os
from pathlib import Path

from devteam_analysis import AnalyzedFailure, Finding

# Never worth searching — vendored deps, VCS, caches, build output. Pruned from the walk so
# resolution stays fast on a big monorepo and never matches a copy inside node_modules/.venv.
_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".turbo",
        "coverage",
        ".tox",
    }
)


def resolve_paths(analysis: AnalyzedFailure, repo_root: str | Path) -> AnalyzedFailure:
    """A copy of ``analysis`` with every finding's file resolved to its real repository path (and
    ``affected_files`` rebuilt from them). Category, summary, symbols, and confidence are kept —
    this layer only fixes paths; it never re-diagnoses."""
    root = Path(repo_root)
    findings = tuple(_resolve_finding(finding, root) for finding in analysis.findings)
    affected: list[str] = []
    for finding in findings:
        if finding.file and finding.file not in affected:
            affected.append(finding.file)
    return AnalyzedFailure(
        category=analysis.category,
        summary=analysis.summary,
        findings=findings,
        affected_files=tuple(affected),
        affected_symbols=analysis.affected_symbols,
        confidence=analysis.confidence,
    )


def _resolve_finding(finding: Finding, root: Path) -> Finding:
    real = _resolve_path(finding.file, root)
    if real is None or real == finding.file:
        return finding
    return Finding(file=real, line=finding.line, code=finding.code, message=finding.message)


def _resolve_path(logical: str, root: Path) -> str | None:
    """The repository-relative path the logical path refers to, or None if it cannot be resolved
    uniquely. An already-real path returns unchanged; otherwise find the unique file whose
    repo-relative path ends with ``logical``."""
    if not logical:
        return None
    if (root / logical).is_file():
        return logical  # already a real repository path
    suffix = Path(logical).parts
    depth = len(suffix)
    name = suffix[-1]
    found: str | None = None
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if name not in filenames:
            continue
        rel = Path(dirpath, name).relative_to(root)
        if rel.parts[-depth:] != suffix:
            continue
        if found is not None:
            return None  # ambiguous — more than one match; leave it for a human/LLM
        found = str(rel)
    return found
