"""ESLintAnalyzer — diagnostic-only FailureAnalyzer for ESLint (ADR 0061).

Understands ESLint's "stylish" output — a file header, then indented ``line:col  error  message
rule`` findings, then a ``✖ N problems`` summary — normalizing ERRORS into findings (warnings are
ignored: they do not fail the build). It proposes NO fixes, reads NO files, produces NO diff.
Recognizes a failure iff it sees the problems summary or ≥1 error finding; else returns None.
"""

from __future__ import annotations

import re

from devteam_analysis.model import AnalyzedFailure, Finding, RawFailure

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\S+Z\s")
# A file header: a JS/TS-ish path, not indented.
_FILE = re.compile(r"^(?P<file>[^\s:]+\.(?:ts|tsx|js|jsx|cjs|mjs|vue))$")
# An indented finding: `  line:col  error|warning  message  rule`.
_FINDING = re.compile(
    r"^\s+(?P<line>\d+):(?P<col>\d+)\s+(?P<sev>error|warning)\s+(?P<msg>.+?)\s{2,}(?P<rule>\S+)$"
)
# The summary: `✖ 8 problems (7 errors, 1 warning)`.
_SUMMARY = re.compile(r"✖\s+(?P<problems>\d+)\s+problems?\s+\((?P<errors>\d+)\s+errors?")
_CATEGORY = "lint"


class ESLintAnalyzer:
    """Normalizes ESLint output into lint diagnostics (errors only). Stateless — reads only logs."""

    def analyze(self, failure: RawFailure) -> AnalyzedFailure | None:
        findings, error_count = _parse(failure.logs)
        if not findings and error_count is None:
            return None
        files = tuple(dict.fromkeys(f.file for f in findings))
        count = error_count if error_count is not None else len(findings)
        return AnalyzedFailure(
            category=_CATEGORY,
            summary=f"ESLint reported {count} error(s).",
            findings=findings,
            affected_files=files,
            confidence=1.0,
        )


def _parse(logs: str) -> tuple[tuple[Finding, ...], int | None]:
    findings: list[Finding] = []
    seen: set[tuple[str, int, int]] = set()
    error_count: int | None = None
    current_file = ""
    for raw in logs.splitlines():
        line = _TIMESTAMP.sub("", raw).rstrip()
        summary = _SUMMARY.search(line)
        if summary is not None:
            error_count = int(summary["errors"])
            continue
        header = _FILE.match(line)
        if header is not None:
            current_file = header["file"]
            continue
        finding = _FINDING.match(line)
        if finding is None or finding["sev"] != "error" or not current_file:
            continue
        key = (current_file, int(finding["line"]), int(finding["col"]))
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            Finding(
                file=current_file,
                line=int(finding["line"]),
                code=finding["rule"],
                message=finding["msg"].strip(),
            )
        )
    return tuple(findings), error_count
