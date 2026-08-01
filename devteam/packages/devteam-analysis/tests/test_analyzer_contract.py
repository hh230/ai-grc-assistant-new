"""Contract tests for the FailureAnalyzer boundary itself — NOT any specific parser (ADR 0061).

Every registered analyzer (``registry.default_analyzers``) must honor the same contract, so the
boundary stays safe as analyzers are added or parsers change. Recognition folds into ``analyze()`` —
it returns None when it does not recognize the failure (the try-parse pattern) — so "recognized"
means "analyze() returned a result"; the contract then pins the SHAPE of every such result.

Parameterized over the shared registry so a newly registered analyzer is covered automatically (and
``test_every_registered_analyzer_has_a_contract_sample`` fails loudly if its sample is missing).
"""

from __future__ import annotations

import pytest
from devteam_analysis import RawFailure, default_analyzers
from devteam_analysis.analyzer import FailureAnalyzer

# A minimal log each analyzer recognizes — just enough to trigger a result. The assertions check the
# generic CONTRACT, never the parse detail, so these stay tiny and tool-shaped.
_SAMPLE: dict[str, str] = {
    "MypyAnalyzer": "app/x.py:1: error: boom  [misc]\n",
    "RuffAnalyzer": "app/x.py:1:1: F401 unused import\n",
    "ESLintAnalyzer": "src/a.ts\n  1:1  error  Bad  no-any\n✖ 1 problem (1 error, 0 warnings)\n",
    "PytestAnalyzer": "FAILED tests/t.py::test_a - AssertionError: nope\n",
    "PNPMAnalyzer": "ERR_PNPM_OUTDATED_LOCKFILE  stale lockfile\n",
}
_HINT: dict[str, str] = {"PNPMAnalyzer": "Run pnpm install"}
_ANALYZERS = default_analyzers()
_IDS = [type(analyzer).__name__ for analyzer in _ANALYZERS]


@pytest.mark.parametrize("analyzer", _ANALYZERS, ids=_IDS)
def test_every_registered_analyzer_has_a_contract_sample(analyzer: FailureAnalyzer) -> None:
    assert type(analyzer).__name__ in _SAMPLE


@pytest.mark.parametrize("analyzer", _ANALYZERS, ids=_IDS)
def test_recognized_result_honors_the_contract(analyzer: FailureAnalyzer) -> None:
    name = type(analyzer).__name__
    result = analyzer.analyze(RawFailure(_HINT.get(name, "step"), _SAMPLE[name]))
    assert result is not None, f"{name} did not recognize its own sample"  # recognized -> not None
    assert result.category.strip(), "category must not be empty"
    assert result.summary.strip(), "summary must not be empty"
    assert 0.0 <= result.confidence <= 1.0, "confidence out of [0, 1]"
    assert all(finding.file.strip() for finding in result.findings), "a Finding.file was empty"
    finding_files = {finding.file for finding in result.findings}
    assert finding_files <= set(result.affected_files), "affected_files misses a finding's file"


@pytest.mark.parametrize("analyzer", _ANALYZERS, ids=_IDS)
@pytest.mark.parametrize(
    "junk",
    ["", "garbage line\n", "\x00\x01 not a log\n", "FAILED\n:::\n-->\nERR_PNPM_\n", "x" * 8000],
)
def test_malformed_log_never_raises(analyzer: FailureAnalyzer, junk: str) -> None:
    # Must never raise on corrupt input: returns None (unrecognized) or a well-formed result.
    result = analyzer.analyze(RawFailure("step", junk))
    assert result is None or result.category.strip()
