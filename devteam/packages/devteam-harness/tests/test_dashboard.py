"""Tests for the run dashboard.

The property that matters most is not layout — it is that a run which did not fully execute can
never be rendered as a pass.
"""

from __future__ import annotations

from pathlib import Path

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.agents.reporter import compile_report
from devteam_harness.dashboard import render_html, summarise, write_html


def _report(*findings: Finding) -> AgentReport:
    report = AgentReport(agent="verifier")
    report.findings.extend(findings)
    report.bump("scenarios", 10)
    return report


def _finding(kind: str, severity: Severity = Severity.CRASH) -> Finding:
    return Finding(
        agent="verifier", severity=severity, kind=kind, detail=f"{kind} happened",
        reproduce="python -m devteam_harness --seed 7", seed=7,
    )


def test_a_clean_run_is_a_pass() -> None:
    totals = summarise(compile_report([_report()]))
    assert totals.verdict == "PASS"
    assert totals.findings == 0


def test_a_run_with_findings_fails() -> None:
    totals = summarise(compile_report([_report(_finding("boom"))]))
    assert totals.verdict == "FAIL"
    assert totals.crashes == 1


def test_a_suspicious_only_run_passes_but_still_reports() -> None:
    """Severity already encodes "would you block a release on this". A live sweep rendered all 42
    pages correctly while the dev server restarted underneath it eight times; the harness
    recovered every time, and calling that FAIL is the kind of inaccuracy that gets a gate
    ignored. The findings are still listed — they are just not a product failure."""
    noise = Finding(
        agent="pilot", severity=Severity.SUSPICIOUS, kind="app_restarted_mid_sweep",
        detail="the server under test restarted", reproduce="open /en/dashboard",
    )
    report = compile_report([_report(noise)])
    totals = summarise(report)
    assert totals.verdict == "PASS"
    assert totals.suspicious == 1
    # Reported, not swallowed.
    assert "app_restarted_mid_sweep" in render_html(report)


def test_an_invariant_violation_still_blocks() -> None:
    """Only CRASH and INVARIANT block. This is the line between the two."""
    violation = Finding(
        agent="verifier", severity=Severity.INVARIANT, kind="plan_dependencies_exist",
        detail="dangling dependency", reproduce="python -m devteam_harness --seed 1",
    )
    assert summarise(compile_report([_report(violation)])).verdict == "FAIL"


def test_a_run_that_did_not_fully_execute_is_INCOMPLETE_not_PASS() -> None:
    """The lie this whole package exists to prevent: '0 failures' while a surface never ran."""
    skipped = Finding(
        agent="pilot", severity=Severity.SUSPICIOUS, kind="browser_unavailable",
        detail="browser coverage did NOT run. This is not a pass.", reproduce="uv sync --extra browser",
    )
    totals = summarise(compile_report([_report(skipped)]))
    assert totals.verdict == "INCOMPLETE", "unmeasured coverage is not a pass"
    assert totals.coverage_gaps == 1


def test_a_timed_out_route_counts_as_unmeasured_not_merely_suspicious() -> None:
    """A request that timed out measured NOTHING about that route. The first live dashboard
    reported 'did not run: 0' while thirteen routes had timed out."""
    timed_out = Finding(
        agent="sentry", severity=Severity.SUSPICIOUS, kind="route_unreachable",
        detail="dashboard: /api/dashboard/export -> TimeoutError", reproduce="curl -i ...",
    )
    totals = summarise(compile_report([_report(timed_out)]))
    assert totals.coverage_gaps == 1
    assert totals.verdict == "INCOMPLETE"


def test_the_coverage_gap_is_stated_in_the_page_not_buried() -> None:
    skipped = Finding(
        agent="sentry", severity=Severity.SUSPICIOUS, kind="surface_unreachable",
        detail="no app answering", reproduce="pnpm dev",
    )
    page = render_html(compile_report([_report(skipped)]))
    assert "INCOMPLETE" in page
    assert "Coverage gap" in page


def test_every_finding_carries_its_reproduce_command() -> None:
    """The first thing anyone does with a bug report is try to see it themselves."""
    page = render_html(compile_report([_report(_finding("boom"))]))
    assert "python -m devteam_harness --seed 7" in page


def test_the_page_is_self_contained() -> None:
    """It must open from a CI artifact zip, offline, with no network."""
    page = render_html(compile_report([_report(_finding("boom"))]))
    for external in ("http://", "https://", "<script"):
        assert external not in page


def test_detail_text_is_escaped() -> None:
    """Findings quote app output; app output is untrusted input (CLAUDE.md 19)."""
    nasty = Finding(
        agent="breaker", severity=Severity.CRASH, kind="xss",
        detail="<img src=x onerror=alert(1)>", reproduce="n/a",
    )
    page = render_html(compile_report([_report(nasty)]))
    assert "<img src=x" not in page
    assert "&lt;img src=x" in page


def test_it_writes_a_file(tmp_path: Path) -> None:
    written = write_html(compile_report([_report()]), tmp_path / "runs" / "index.html")
    assert written.exists()
    assert "PASS" in written.read_text(encoding="utf-8")
