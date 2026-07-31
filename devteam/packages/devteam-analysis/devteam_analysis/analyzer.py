"""The FailureAnalyzer boundary — the ONLY tool-aware layer (ADR 0061).

A ``FailureAnalyzer`` recognizes ONE kind of failure (mypy, pytest, eslint, …) and normalizes it
into an ``AnalyzedFailure``, or returns ``None`` if it does not recognize the failure so the next
analyzer can try. A genuine Port (Port-Worthiness): multiple independent realizations are the point.
The ``analyze_failure`` dispatcher is generic — first analyzer that recognizes the failure wins.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from devteam_analysis.model import AnalyzedFailure, RawFailure


@runtime_checkable
class FailureAnalyzer(Protocol):
    """Normalizes one recognized failure kind into an AnalyzedFailure, else returns None."""

    def analyze(self, failure: RawFailure) -> AnalyzedFailure | None: ...


def analyze_failure(
    failure: RawFailure, analyzers: Sequence[FailureAnalyzer]
) -> AnalyzedFailure | None:
    """First analyzer that recognizes the failure wins; None if none do. No tool knowledge here."""
    for analyzer in analyzers:
        result = analyzer.analyze(failure)
        if result is not None:
            return result
    return None
