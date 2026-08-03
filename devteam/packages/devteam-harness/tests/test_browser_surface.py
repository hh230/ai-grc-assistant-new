"""Tests for the browser surface and the Pilot agent.

These run WITHOUT launching a browser: judgement is tested against constructed observations, so
the rules stay verifiable in CI even where Chromium is not installed. The one thing that DOES
need a browser — that it drives a real page — is proven by the live sweep recorded in the PR, not
by a test that would silently skip.
"""

from __future__ import annotations

import json
from pathlib import Path

from devteam_harness.agents import pilot
from devteam_harness.agents.base import Severity
from devteam_harness.surfaces.browser import (
    VIEWPORTS,
    BrowserSurface,
    PageObservation,
    playwright_available,
)


def _observation(**overrides: object) -> PageObservation:
    base = {"url": "/en/dashboard", "locale": "en", "viewport": "desktop", "status": 200}
    base.update(overrides)
    return PageObservation(**base)  # type: ignore[arg-type]


# --- the defect a status check cannot see -----------------------------------------------------


def test_http_200_with_an_error_boundary_is_a_crash() -> None:
    """The reason this agent exists.

    Next.js `error.tsx` returns 200 while showing "something went wrong", so an HTTP-only sweep
    calls a visibly broken page healthy.
    """
    observation = _observation(visible_text="Something went wrong. Try again.")
    assert observation.showed_error_boundary
    assert not observation.is_healthy

    report = pilot.AgentReport(agent=pilot.AGENT)
    pilot._judge(report, observation)
    kinds = {finding.kind for finding in report.findings}
    assert "error_boundary_rendered" in kinds
    assert report.findings[0].severity is Severity.CRASH


def test_the_arabic_error_boundary_is_detected_too() -> None:
    """A crash the Arabic-speaking half of the users see must not be invisible to the harness."""
    assert _observation(visible_text="واجهت هذه الصفحة مشكلة غير متوقعة").showed_error_boundary


def test_a_healthy_page_produces_no_findings() -> None:
    observation = _observation(visible_text="Dashboard — coverage 62%")
    assert observation.is_healthy
    report = pilot.AgentReport(agent=pilot.AGENT)
    pilot._judge(report, observation)
    assert not report.findings
    assert report.stats["healthy"] == 1


# --- severity grading -------------------------------------------------------------------------


def test_an_uncaught_exception_is_a_crash_even_on_a_page_that_looks_fine() -> None:
    """Silent death in a compliance product is how wrong data gets shown."""
    observation = _observation(
        visible_text="Risk Register", page_errors=["TypeError: x is not a function\n  at foo"]
    )
    assert not observation.is_healthy
    report = pilot.AgentReport(agent=pilot.AGENT)
    pilot._judge(report, observation)
    assert report.findings[0].kind == "uncaught_exception"
    assert report.findings[0].severity is Severity.CRASH


def test_console_errors_are_suspicious_not_crashes() -> None:
    """Grading third-party console noise as a failure would train people to ignore the report."""
    observation = _observation(visible_text="Policies", console_errors=["favicon 404"])
    report = pilot.AgentReport(agent=pilot.AGENT)
    pilot._judge(report, observation)
    assert [finding.severity for finding in report.findings] == [Severity.SUSPICIOUS]


def test_a_5xx_api_call_behind_a_rendered_page_is_still_reported() -> None:
    observation = _observation(
        visible_text="Evidence", server_error_requests=["500 /api/evidence"]
    )
    report = pilot.AgentReport(agent=pilot.AGENT)
    pilot._judge(report, observation)
    assert report.findings[0].kind == "page_request_5xx"


# --- the anti-false-confidence property -------------------------------------------------------


def test_a_missing_browser_is_reported_not_silently_skipped(monkeypatch: object) -> None:
    """`apps/web`'s eval scripts print SKIP and exit 0, so CI passes while verifying nothing."""
    monkeypatch.setattr(pilot, "playwright_available", lambda: False)  # type: ignore[attr-defined]
    report = pilot.run()
    assert report.findings, "an unavailable browser must produce a finding"
    assert report.findings[0].kind == "browser_unavailable"
    assert "not a pass" in report.findings[0].detail


def test_the_optional_dependency_is_actually_installed_here() -> None:
    """Not a skip guard — a statement that the dev environment can run browser coverage.
    If this fails, `uv sync --extra browser` was not run and the live sweep is not being done."""
    assert playwright_available()


# --- coverage shape ---------------------------------------------------------------------------


def test_mobile_is_a_first_class_viewport() -> None:
    """RTL Arabic at 390px is where layout defects actually surface."""
    assert "mobile" in VIEWPORTS
    assert VIEWPORTS["mobile"][0] < VIEWPORTS["desktop"][0]


def test_artifacts_carry_the_stack_trace_not_just_a_picture() -> None:
    """A screenshot of a broken page without the trace behind it is a bug report nobody can act
    on. The four artifacts must travel together."""
    from devteam_harness.surfaces import browser

    observation = _observation(
        visible_text="Something went wrong",
        page_errors=["TypeError: boom\n  at Component"],
        console_errors=["failed to fetch"],
        server_error_requests=["500 /api/risks"],
    )
    directory = Path("artifacts-test")
    browser._capture(_FakePage(), observation, directory)
    payload = json.loads((directory / "en_desktop_en_dashboard.json").read_text(encoding="utf-8"))

    assert payload["stack_traces"] == ["TypeError: boom\n  at Component"]
    assert payload["console_errors"] == ["failed to fetch"]
    assert payload["server_error_requests"] == ["500 /api/risks"]
    assert payload["showed_error_boundary"] is True

    for leftover in directory.iterdir():
        leftover.unlink()
    directory.rmdir()


def test_a_page_too_broken_to_photograph_still_yields_its_other_artifacts() -> None:
    """The console and stack trace are exactly what you need when the screenshot fails."""
    from devteam_harness.surfaces import browser

    directory = Path("artifacts-test-crash")
    result = browser._capture(_ExplodingPage(), _observation(url="/en/plan"), directory)
    assert result is None
    assert (directory / "en_desktop_en_plan.json").exists()

    for leftover in directory.iterdir():
        leftover.unlink()
    directory.rmdir()


def test_a_listed_page_that_404s_is_a_defect_not_a_pass() -> None:
    """A 404 means the route was deleted or the inventory is lying about its coverage. The first
    authenticated sweep scored a non-existent `/documents` page as healthy; that is exactly the
    silent coverage loss `routes.py` promises to make visible."""
    observation = _observation(status=404, visible_text="404 This page could not be found")
    assert not observation.is_healthy
    report = pilot.AgentReport(agent=pilot.AGENT)
    pilot._judge(report, observation)
    assert "page_missing" in {finding.kind for finding in report.findings}


def test_every_inventoried_page_exists_in_the_app() -> None:
    """Catches an invented page at import time rather than after a 20-minute browser sweep."""
    from pathlib import Path

    from devteam_harness.surfaces.routes import PAGES

    app_dir = Path(__file__).resolve().parents[4] / "apps/web/app/[locale]/(app)"
    if not app_dir.is_dir():  # pragma: no cover - only when run outside the monorepo
        return
    for page in PAGES:
        assert (app_dir / page.lstrip("/")).is_dir(), f"{page} is in PAGES but has no route"


def test_evidence_follows_the_finding_not_the_verdict() -> None:
    """A console error does not make a page unhealthy, but it DOES produce a finding — and a
    finding whose reproduce line points at artifacts that were never written is a dead end.
    This gap was real: the first authenticated sweep filed four console-error findings whose
    artifacts did not exist."""
    noisy = _observation(visible_text="Documents", console_errors=["404 loading /foo.js"])
    assert noisy.is_healthy, "console noise alone is not a failure"
    assert noisy.needs_artifacts, "but it still needs evidence"

    clean = _observation(visible_text="Documents")
    assert not clean.needs_artifacts, "a clean page should not leave artifacts behind"


def test_the_surface_defaults_point_at_the_dev_server() -> None:
    assert BrowserSurface().base_url == "http://localhost:3000"


class _FakePage:
    def screenshot(self, *, path: str, full_page: bool) -> None:
        Path(path).write_bytes(b"\x89PNG")

    def evaluate(self, _script: str) -> str:
        return ""


class _ExplodingPage:
    def screenshot(self, *, path: str, full_page: bool) -> None:
        raise RuntimeError("target page has been closed")

    def evaluate(self, _script: str) -> str:
        return ""
