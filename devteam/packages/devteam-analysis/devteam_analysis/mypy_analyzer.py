"""MypyAnalyzer — a diagnostic-only FailureAnalyzer for mypy (ADR 0061).

Tool knowledge lives HERE, never in the Developer — but it ends at UNDERSTANDING. Like a compiler or
a language server, it parses ``file:line: error: msg [code]`` into normalized findings, names the
affected files/symbols, and reports confidence. It proposes NO edits and makes NO fix decisions —
how to fix a type error is the Developer's call. Recognizes a failure iff it finds ≥1 mypy error
line; else returns None so the dispatcher tries the next analyzer.
"""

from __future__ import annotations

import re

from devteam_analysis.model import AnalyzedFailure, Finding, RawFailure

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\S+Z\s")
# One mypy error: file.py[:LINE[:COL]]: error: message  [error-code].
# LINE and code are OPTIONAL — module-level errors (e.g. duplicate module) carry neither.
_MYPY_ERROR = re.compile(
    r"^(?P<file>[^:\n]+\.py):"
    r"(?:(?P<line>\d+)(?::\d+)?:)?"
    r"\s*error:\s+"
    r"(?P<msg>.*?)(?:  \[(?P<code>[\w-]+)\])?$"
)
_QUOTED = re.compile(r'"([^"]+)"')
_CATEGORY = "type_check"


class MypyAnalyzer:
    """Normalizes mypy failures into diagnostics. Stateless — it reads only the logs, never the repo
    (reading source and deciding a fix is the Developer's job, not the analyzer's)."""

    def analyze(self, failure: RawFailure) -> AnalyzedFailure | None:
        findings = _parse(failure.logs)
        if not findings:
            return None
        files = tuple(dict.fromkeys(f.file for f in findings))
        symbols = tuple(
            dict.fromkeys(
                s for f in findings for s in _QUOTED.findall(f.message) if "/" not in s
            )
        )
        return AnalyzedFailure(
            category=_CATEGORY,
            summary=f"Type checking reported {len(findings)} error(s).",
            findings=findings,
            affected_files=files,
            affected_symbols=symbols,
            confidence=1.0,
        )


def _parse(logs: str) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    seen: set[tuple[str, int, str]] = set()
    for raw in logs.splitlines():
        match = _MYPY_ERROR.match(_TIMESTAMP.sub("", raw).rstrip())
        if match is None:
            continue
        line = int(match["line"]) if match["line"] else 0
        key = (match["file"], line, match["msg"])
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            Finding(  # line 0 = module-level error (no line number)
                file=match["file"], line=line, code=match["code"] or "", message=match["msg"]
            )
        )
    return tuple(findings)
