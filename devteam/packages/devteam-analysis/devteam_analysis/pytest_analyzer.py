"""PytestAnalyzer — diagnostic-only FailureAnalyzer for pytest (ADR 0061).

Understands pytest's short summary — ``FAILED path::test - ExceptionType: message`` — and normalizes
each failing test into a diagnostic: the test's file, the exception type (as the code), and the
detail. It does NOT explain WHY the test failed, proposes NO fix, reads NO files, produces NO diff.
Recognizes a failure iff ≥1 ``FAILED`` line is present; else returns None.
"""

from __future__ import annotations

import re

from devteam_analysis.model import AnalyzedFailure, Finding, RawFailure

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\S+Z\s")
# A failing test: `FAILED path::test[params]` with an optional ` - detail`.
_FAILED = re.compile(r"^FAILED\s+(?P<file>[^\s:]+)::(?P<test>\S+?)(?:\s+-\s+(?P<detail>.*))?$")
# The leading exception type in the detail: `AssertionError: ...`, `TypeError: ...`.
_EXCEPTION = re.compile(r"^(?P<exc>[A-Za-z_]\w*(?:Error|Exception|Warning)):")
_CATEGORY = "tests"


class PytestAnalyzer:
    """Normalizes pytest's failing-test summary into diagnostics. Reads only the logs."""

    def analyze(self, failure: RawFailure) -> AnalyzedFailure | None:
        findings = _parse(failure.logs)
        if not findings:
            return None
        files = tuple(dict.fromkeys(f.file for f in findings))
        return AnalyzedFailure(
            category=_CATEGORY,
            summary=f"pytest reported {len(findings)} failing test(s).",
            findings=findings,
            affected_files=files,
            confidence=1.0,
        )


def _parse(logs: str) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for raw in logs.splitlines():
        match = _FAILED.match(_TIMESTAMP.sub("", raw).rstrip())
        if match is None:
            continue
        key = (match["file"], match["test"])
        if key in seen:
            continue
        seen.add(key)
        detail = (match["detail"] or "").strip()
        exception = _EXCEPTION.match(detail)
        code = exception["exc"] if exception is not None else ""
        findings.append(
            Finding(
                file=match["file"],
                line=0,
                code=code,
                message=detail if detail else match["test"],
            )
        )
    return tuple(findings)
