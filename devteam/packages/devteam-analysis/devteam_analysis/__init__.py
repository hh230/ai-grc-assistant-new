"""Autonomous Platform Dev Team — failure analysis (ADR 0061).

The tool-aware layer that sits UNDER the general Developer: a ``FailureAnalyzer`` normalizes raw CI
failure logs into a tool-agnostic ``AnalyzedFailure`` (category, findings, edits). Analyzers may
exist per tool (mypy, pytest, eslint, …); the Developer consumes only the normalized model and never
learns which tool failed. New failure kinds are added by writing an analyzer — no Developer or Core
change (§17).
"""

from devteam_analysis.analyzer import FailureAnalyzer, analyze_failure
from devteam_analysis.eslint_analyzer import ESLintAnalyzer
from devteam_analysis.model import AnalyzedFailure, Finding, RawFailure
from devteam_analysis.mypy_analyzer import MypyAnalyzer
from devteam_analysis.pnpm_analyzer import PNPMAnalyzer
from devteam_analysis.pytest_analyzer import PytestAnalyzer
from devteam_analysis.registry import default_analyzers
from devteam_analysis.ruff_analyzer import RuffAnalyzer

__all__ = [
    "AnalyzedFailure",
    "ESLintAnalyzer",
    "FailureAnalyzer",
    "Finding",
    "MypyAnalyzer",
    "PNPMAnalyzer",
    "PytestAnalyzer",
    "RawFailure",
    "RuffAnalyzer",
    "analyze_failure",
    "default_analyzers",
]
