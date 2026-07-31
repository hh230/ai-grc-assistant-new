"""RuffAnalyzer — diagnostic-only FailureAnalyzer for ``ruff check`` (ADR 0061).

Understands Ruff's output in BOTH layouts and normalizes it into lint findings:
  * concise: ``path:line:col: CODE message``
  * full (default): a ``CODE [*] message`` line followed by a ``--> path:line:col`` line.
It proposes NO fixes, reads NO files, produces NO diff. Recognizes a failure iff ≥1 Ruff violation
is present; else returns None so the dispatcher tries the next analyzer.
"""

from __future__ import annotations

import re

from devteam_analysis.model import AnalyzedFailure, Finding, RawFailure

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\S+Z\s")
# Concise: path:line:col: CODE message  (CODE is a rule id like F401, E402, RUF100).
_CONCISE = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>\d+):(?P<col>\d+): (?P<code>[A-Z]+\d+) (?P<msg>.*)$"
)
# Full: a `CODE [*] message` line, then a `--> file:line:col` line ([*] marks a fixable rule).
_FULL_CODE = re.compile(r"^(?P<code>[A-Z]+\d+)(?: \[\*\])? (?P<msg>.+)$")
_FULL_LOC = re.compile(r"^\s*-->\s+(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+)\s*$")
_CATEGORY = "lint"


class RuffAnalyzer:
    """Normalizes ``ruff check`` output into lint diagnostics. Stateless — reads only the logs."""

    def analyze(self, failure: RawFailure) -> AnalyzedFailure | None:
        findings = _parse(failure.logs)
        if not findings:
            return None
        files = tuple(dict.fromkeys(f.file for f in findings))
        return AnalyzedFailure(
            category=_CATEGORY,
            summary=f"Ruff reported {len(findings)} lint violation(s).",
            findings=findings,
            affected_files=files,
            confidence=1.0,
        )


def _parse(logs: str) -> tuple[Finding, ...]:
    lines = [_TIMESTAMP.sub("", raw).rstrip() for raw in logs.splitlines()]
    findings: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for index, line in enumerate(lines):
        concise = _CONCISE.match(line)
        if concise is not None:
            _add(
                findings,
                seen,
                concise["file"],
                int(concise["line"]),
                concise["code"],
                concise["msg"],
            )
            continue
        code = _FULL_CODE.match(line)
        if code is None or index + 1 >= len(lines):
            continue
        loc = _FULL_LOC.match(lines[index + 1])
        if loc is not None:
            _add(findings, seen, loc["file"], int(loc["line"]), code["code"], code["msg"])
    return tuple(findings)


def _add(
    findings: list[Finding],
    seen: set[tuple[str, int, str]],
    file: str,
    line: int,
    code: str,
    message: str,
) -> None:
    key = (file, line, code)
    if key in seen:
        return
    seen.add(key)
    findings.append(Finding(file=file, line=line, code=code, message=message.strip()))
