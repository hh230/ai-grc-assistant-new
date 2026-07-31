"""The registered FailureAnalyzers — the single source of truth for the analyzer set (ADR 0061).

Both the dispatcher and the contract test read this list, so they can never drift. A new analyzer is
registered by adding one line here — the ONLY change required (no Developer, Core, Protocol, or
dispatcher-logic change). Order is dispatcher precedence: PNPM is last because its generic 'command
failed' fallback must not steal a real tool's output (a `pnpm lint` failure is ESLint).
"""

from __future__ import annotations

from devteam_analysis.analyzer import FailureAnalyzer
from devteam_analysis.eslint_analyzer import ESLintAnalyzer
from devteam_analysis.mypy_analyzer import MypyAnalyzer
from devteam_analysis.pnpm_analyzer import PNPMAnalyzer
from devteam_analysis.pytest_analyzer import PytestAnalyzer
from devteam_analysis.ruff_analyzer import RuffAnalyzer


def default_analyzers() -> list[FailureAnalyzer]:
    """Every registered analyzer, in dispatch order."""
    return [
        MypyAnalyzer(),
        RuffAnalyzer(),
        ESLintAnalyzer(),
        PytestAnalyzer(),
        PNPMAnalyzer(),
    ]
