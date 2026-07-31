"""The normalized failure model — the diagnostic the Developer reasons over (ADR 0061).

A ``FailureAnalyzer`` turns raw CI failure logs into an ``AnalyzedFailure``: a diagnosis of WHAT
failed and WHERE — category, summary, structured findings, affected files/symbols, confidence. It is
purely DIAGNOSTIC: analyzers understand (like a compiler or language server), they never engineer —
no edits, no fix decisions. Nothing here names a tool or proposes a change. The Developer consumes
this model and is the ONLY layer that decides how to fix it, which files to modify, and what diff to
produce.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawFailure:
    """The input to analysis: the failing step's name (a hint only) and its raw log text."""

    tool_hint: str
    logs: str


@dataclass(frozen=True)
class Finding:
    """One structured diagnostic — where and what. Never a fix; that is the Developer's job."""

    file: str
    line: int
    code: str
    message: str


@dataclass(frozen=True)
class AnalyzedFailure:
    """The normalized diagnostic the Developer consumes. ``category`` is a generic class
    (type_check, tests, lint, build, dependencies, unknown); ``summary`` is the diagnosis; findings
    are the structured diagnostics; ``affected_files``/``affected_symbols`` locate the blast radius;
    ``confidence`` is how sure the analyzer is. It carries NO edits and makes NO fix decisions — the
    Developer decides all of that. No tool name appears — the Developer stays a general engineer."""

    category: str
    summary: str
    findings: tuple[Finding, ...] = ()
    affected_files: tuple[str, ...] = ()
    affected_symbols: tuple[str, ...] = ()
    confidence: float = 1.0
