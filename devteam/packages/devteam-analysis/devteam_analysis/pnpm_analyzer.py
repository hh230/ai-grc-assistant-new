"""PNPMAnalyzer — diagnostic-only FailureAnalyzer for pnpm (ADR 0061).

Understands pnpm's error codes — ``ERR_PNPM_OUTDATED_LOCKFILE``, ``ERR_PNPM_FETCH_404``, … — and the
generic ``Command failed with exit code N`` (only treated as pnpm on a pnpm step, via the tool hint,
so it never steals a real tool's failure). It proposes NO fix (never ``pnpm install`` or anything),
reads NO files, produces NO diff. Recognizes a failure iff it finds a pnpm error signal; else None.
"""

from __future__ import annotations

import re

from devteam_analysis.model import AnalyzedFailure, Finding, RawFailure

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\S+Z\s")
# A pnpm error code and its message: `ERR_PNPM_<CODE>  message`.
_PNPM_ERR = re.compile(r"(?P<code>ERR_PNPM_[A-Z0-9_]+)(?:\s+(?P<msg>.*))?$")
_COMMAND_FAILED = re.compile(r"Command failed with exit code \d+")
_CATEGORY = "package_manager"
# pnpm errors are not source-located; the lockfile is the file they relate to (and often the fix).
_MANIFEST = "pnpm-lock.yaml"


class PNPMAnalyzer:
    """Normalizes pnpm errors into diagnostics. Reads only the logs (and the tool hint)."""

    def analyze(self, failure: RawFailure) -> AnalyzedFailure | None:
        findings = _parse(failure.logs)
        if findings:
            return _build(findings)
        # A bare "Command failed with exit code N" is only a pnpm signal on a pnpm step.
        if "pnpm" in failure.tool_hint.lower() and _COMMAND_FAILED.search(failure.logs):
            return _build([Finding(file=_MANIFEST, line=0, code="", message="pnpm command failed")])
        return None


def _build(findings: list[Finding]) -> AnalyzedFailure:
    return AnalyzedFailure(
        category=_CATEGORY,
        summary=f"pnpm reported {len(findings)} error(s).",
        findings=tuple(findings),
        affected_files=tuple(dict.fromkeys(f.file for f in findings)),
        confidence=1.0,
    )


def _parse(logs: str) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[str] = set()
    for raw in logs.splitlines():
        match = _PNPM_ERR.search(_TIMESTAMP.sub("", raw).rstrip())
        if match is None:
            continue
        code = match["code"]
        if code in seen:
            continue
        seen.add(code)
        message = (match["msg"] or "").strip() or code
        findings.append(Finding(file=_MANIFEST, line=0, code=code, message=message))
    return findings
