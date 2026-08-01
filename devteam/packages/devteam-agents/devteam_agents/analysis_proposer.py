"""AnalysisProposer — the Developer's engineering over a (diagnostic-only) AnalyzedFailure.

The Developer is the ENGINEER (ADR 0061): it consumes the analyzer's diagnosis and DECIDES the fix —
how to fix it, which files to change, what diff. The analyzer only understood the failure;
all engineering lives here. It emits the Developer's outputs — diagnosis, reasoning, an
implementation plan, and a diff it builds by reading the affected source and applying a fix strategy
it owns. The current strategy is deterministic (a category+language convention: a Python type-check
failure gets a targeted ``# type: ignore``); a future LLM Developer reasons a real fix over the same
model. No tool knowledge — the Developer never learns which tool failed, and stays general.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devteam_analysis import AnalyzedFailure, Finding
from devteam_protocol import AgentArtifact, AgentRequest, AgentRole

_CONTEXT = 3  # unchanged lines on each side of a change — a standard unified diff (git's default)
_NO_NEWLINE = "\\ No newline at end of file"
_SourceCache = dict[str, "tuple[list[str], bool] | None"]


class AnalysisProposer:
    """Bind to an AnalyzedFailure + repo root; calling it returns the Developer's artifacts. The
    Developer reads the affected files (its input) and decides the diff — it is a PatchProposer."""

    def __init__(self, analysis: AnalyzedFailure, repo_root: str | Path = ".") -> None:
        self._analysis = analysis
        self._repo_root = Path(repo_root)

    def __call__(self, request: AgentRequest) -> Sequence[AgentArtifact]:
        analysis = self._analysis
        artifacts = [
            _artifact("diagnosis", "failure diagnosis", _diagnose(analysis)),
            _artifact("reasoning", "reasoning", _reason(analysis)),
            _artifact("plan", "implementation plan", _plan(analysis)),
        ]
        diff = self._engineer_diff()
        if diff:
            artifacts.append(_artifact("diff", "proposed change", diff))
        return artifacts

    def _engineer_diff(self) -> str:
        """The Developer's engineering decision: how to fix each diagnostic. Deterministic today; an
        LLM Developer would reason a real fix here over the same findings."""
        hunks: list[str] = []
        cache: _SourceCache = {}
        for finding in self._analysis.findings:
            hunk = self._fix(finding, cache)
            if hunk is not None:
                hunks.append(hunk)
        return "\n".join(hunks)

    def _fix(self, finding: Finding, cache: _SourceCache) -> str | None:
        if finding.line <= 0:
            return None  # module-level error (no line) — not line-suppressible; leave for an LLM
        suffix = _suppression(self._analysis.category, finding.file, finding.code)
        if suffix is None:
            return None  # no deterministic strategy for this category/language — leave for an LLM
        source = _read_source(self._repo_root, finding.file, cache)
        if source is None:
            return None  # can't read real source → decline; never a diff that won't apply
        lines, ends_with_newline = source
        if not (1 <= finding.line <= len(lines)):
            return None
        idx = finding.line - 1
        if suffix.strip() in lines[idx]:
            return None  # already applied on that line
        return _unified_hunk(finding.file, lines, idx, lines[idx] + suffix, ends_with_newline)


def _suppression(category: str, file: str, code: str) -> str | None:
    """The Developer's language/category convention for a quick, deterministic fix — owned by the
    engineer, not the analyzer. Extend with real fixes or more languages as strategies are added."""
    if category == "type_check" and file.endswith(".py"):
        return f"  # type: ignore[{code}]" if code else "  # type: ignore"
    return None


def _unified_hunk(
    file: str, lines: list[str], idx: int, fixed: str, ends_with_newline: bool
) -> str:
    """A STANDARD unified diff replacing line ``idx`` with ``fixed``, carrying ``_CONTEXT`` context
    lines each side (clamped to the file) — enough that plain ``git apply`` accepts it, plus the
    ``\\ No newline`` marker when the changed hunk reaches an unterminated final line."""
    start = max(0, idx - _CONTEXT)
    end = min(len(lines) - 1, idx + _CONTEXT)
    last = len(lines) - 1
    count = end - start + 1
    body: list[str] = []
    for i in range(start, end + 1):
        no_newline = i == last and not ends_with_newline
        if i == idx:
            body.append(f"-{lines[i]}")
            if no_newline:
                body.append(_NO_NEWLINE)
            body.append(f"+{fixed}")
        else:
            body.append(f" {lines[i]}")
        if no_newline:
            body.append(_NO_NEWLINE)
    header = f"@@ -{start + 1},{count} +{start + 1},{count} @@"
    return f"--- a/{file}\n+++ b/{file}\n{header}\n" + "\n".join(body) + "\n"


def _read_source(repo_root: Path, file: str, cache: _SourceCache) -> tuple[list[str], bool] | None:
    """The affected file's lines + whether it ends with a newline, read from the working tree (the
    Developer's input). None if the file is not available locally — the Developer then declines."""
    if file not in cache:
        path = repo_root / file
        try:
            text = path.read_text(encoding="utf-8") if path.is_file() else None
        except OSError:
            text = None
        cache[file] = (text.splitlines(), text.endswith("\n")) if text is not None else None
    return cache[file]


def _artifact(kind: str, title: str, content: str) -> AgentArtifact:
    return AgentArtifact(kind=kind, title=title, content=content, produced_by=AgentRole.DEVELOPER)


def _diagnose(analysis: AnalyzedFailure) -> str:
    if not analysis.findings:
        return f"The {analysis.category} step failed, but no diagnostics were recognized."
    lines = [
        f"{analysis.summary} (category {analysis.category}, confidence {analysis.confidence:.0%})"
    ]
    if analysis.affected_files:
        lines.append(f"Affected files: {', '.join(analysis.affected_files)}.")
    if analysis.affected_symbols:
        lines.append(f"Affected symbols: {', '.join(analysis.affected_symbols)}.")
    lines.append("Diagnostics:")
    lines += [
        f"  - {f.file}:{f.line}: {f.message}" + (f" [{f.code}]" if f.code else "")
        for f in analysis.findings
    ]
    return "\n".join(lines)


def _reason(analysis: AnalyzedFailure) -> str:
    count = len(analysis.findings)
    if not count:
        return "Without recognized diagnostics, no targeted fix can be decided deterministically."
    return (
        f"Each diagnostic is a concrete defect at a known location; fixing all {count} clears the "
        f"failing {analysis.category} step. They are independent, so one change can address them."
    )


def _plan(analysis: AnalyzedFailure) -> str:
    if not analysis.findings:
        return "1. Add an analyzer for this failure category.\n2. Re-run CI."
    steps = [
        f"{i}. Fix {f.file}:{f.line} — {f.message}"
        for i, f in enumerate(analysis.findings, start=1)
    ]
    steps.append(f"{len(steps) + 1}. Re-run CI to confirm the {analysis.category} step passes.")
    return "\n".join(steps)
