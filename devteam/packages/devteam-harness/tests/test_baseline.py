"""Tests for the regression gate.

The gate's only job is to answer "did this change make anything worse than it already was". The
tests below are the ways that question can be answered wrongly.
"""

from __future__ import annotations

from pathlib import Path

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.agents.reporter import Report, compile_report
from devteam_harness.baseline import compare, counts_from, write_baseline


def _report(*kinds: str) -> Report:
    report = AgentReport(agent="verifier")
    for kind in kinds:
        report.findings.append(
            Finding(
                agent="verifier",
                severity=Severity.INVARIANT,
                kind=kind,
                detail=f"{kind} happened",
                reproduce="python -m devteam_harness --seed 1",
            )
        )
    return compile_report([report])


def test_a_known_failure_does_not_block_a_release(tmp_path: Path) -> None:
    """A permanently red gate is ignored within a week, and then protects nothing. One real
    defect is currently known and unfixed; it must not make every release red."""
    baseline = tmp_path / "baseline.json"
    write_baseline(_report("plan_dependencies_exist"), baseline, scenarios=100)

    result = compare(_report("plan_dependencies_exist"), baseline, scenarios=100)
    assert result.ok
    assert "PASS" in result.render()


def test_a_new_kind_of_failure_blocks(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    write_baseline(_report("plan_dependencies_exist"), baseline, scenarios=100)

    result = compare(
        _report("plan_dependencies_exist", "brand_new_crash"), baseline, scenarios=100
    )
    assert not result.ok
    assert "brand_new_crash" in result.new_kinds
    assert "regression" in result.render()


def test_a_known_failure_getting_worse_blocks(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    write_baseline(_report("flaky"), baseline, scenarios=100)

    result = compare(_report("flaky", "flaky", "flaky"), baseline, scenarios=100)
    assert not result.ok
    assert result.worsened["flaky"] == (1, 3)


def test_counts_are_normalised_across_run_sizes(tmp_path: Path) -> None:
    """7 violations in 40 scenarios is not 7 in 1000. Comparing raw counts would call a smaller
    run an improvement and a larger one a regression, both wrongly."""
    baseline = tmp_path / "baseline.json"
    write_baseline(_report(*["flaky"] * 10), baseline, scenarios=100)

    # Same RATE, half the scenarios — not a regression.
    assert compare(_report(*["flaky"] * 5), baseline, scenarios=50).ok
    # Double the rate at half the scenarios — a regression.
    assert not compare(_report(*["flaky"] * 10), baseline, scenarios=50).ok


def test_a_missing_baseline_is_strict_not_permissive(tmp_path: Path) -> None:
    """Being wrongly red is recoverable in one command; being wrongly green is how a regression
    ships."""
    result = compare(_report("something"), tmp_path / "absent.json", scenarios=100)
    assert not result.ok


def test_a_coverage_gap_blocks_even_with_no_regression(tmp_path: Path) -> None:
    """'Nothing got worse' means nothing if the checks did not run."""
    baseline = tmp_path / "baseline.json"
    write_baseline(_report("browser_unavailable"), baseline, scenarios=100)

    result = compare(_report("browser_unavailable"), baseline, scenarios=100)
    assert not result.ok, "unmeasured coverage is never a pass, baselined or not"
    assert "NOT RUN" in result.render()


def test_a_coverage_gap_is_never_written_into_the_baseline(tmp_path: Path) -> None:
    """A baseline records known PRODUCT defects. Recording "this check did not run" would bake a
    blind spot into the gate permanently. The first generated baseline tried to do exactly that,
    picking up a route_unreachable timeout caused by load on the machine."""
    baseline = tmp_path / "baseline.json"
    write_baseline(_report("plan_dependencies_exist", "route_unreachable"), baseline, scenarios=100)

    text = baseline.read_text(encoding="utf-8")
    assert "plan_dependencies_exist" in text
    assert "route_unreachable" not in text


def test_a_fixed_defect_does_not_block_but_is_reported(tmp_path: Path) -> None:
    """A fix must never block a release. But a kind that vanished can also mean the check stopped
    running, and a stale baseline is a gate that has quietly stopped gating."""
    baseline = tmp_path / "baseline.json"
    write_baseline(_report("old_bug"), baseline, scenarios=100)

    result = compare(_report(), baseline, scenarios=100)
    assert result.ok
    assert result.baseline_is_stale
    assert "refresh the baseline" in result.render()


def test_the_baseline_file_is_reviewable(tmp_path: Path) -> None:
    """Raising it must be a deliberate act with a diff and a reviewer."""
    baseline = tmp_path / "baseline.json"
    write_baseline(_report("a", "b", "b"), baseline, scenarios=250)
    text = baseline.read_text(encoding="utf-8")
    assert '"scenarios": 250' in text
    assert '"b": 2' in text
    assert text.endswith("\n")


def test_counts_from_groups_by_kind() -> None:
    assert counts_from(_report("x", "x", "y")) == {"x": 2, "y": 1}
