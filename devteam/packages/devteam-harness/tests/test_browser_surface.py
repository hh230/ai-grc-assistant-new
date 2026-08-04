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


def test_a_server_restart_is_reported_but_does_not_condemn_the_page() -> None:
    """A live sweep hit a `next dev` worker crash: its supervisor respawned it, and every
    remaining page in the run failed with ERR_CONNECTION_REFUSED — a cascade that said nothing
    about those pages. The surface now waits for recovery and retries; the restart is still
    surfaced, because it explains the gap and is the mechanism behind the intermittent
    "something went wrong" users report."""
    observation = _observation(visible_text="Dashboard", recovered_from_restart=True)
    assert observation.is_healthy, "a page that loaded after the retry is not broken"

    report = pilot.AgentReport(agent=pilot.AGENT)
    pilot._judge(report, observation)
    kinds = {finding.kind for finding in report.findings}
    assert kinds == {"app_restarted_mid_sweep"}, "the restart is reported, and only the restart"
    assert report.stats["restarts_survived"] == 1


def test_a_failed_relogin_does_not_claim_the_session_died() -> None:
    """Observed live: after a worker restart the re-login attempt failed, yet the retried page
    rendered the full signed-in shell — the cookie had survived. Recording `authenticated=False`
    there would silently disable the `session_lost` guard, so a failed attempt must not downgrade
    a session it did not disprove. `landed_on_login` is the evidence, not the attempt's result."""
    import inspect

    from devteam_harness.surfaces import browser

    source = inspect.getsource(browser.BrowserSurface.visit)
    assert "self._login() or self._authenticated" in source


def test_a_rate_limited_signin_is_honoured_not_fought() -> None:
    """The app rate-limits sign-in (8 attempts / 60s) as brute-force protection and answers 429
    with Retry-After. The harness must honour that rather than fight a real security control or
    misreport it as a broken login.

    Defensive: the app resets the counter on a SUCCESSFUL sign-in, so the harness's own logins do
    not normally trip it. This covers the path that exists, not one observed in a run."""
    from devteam_harness.surfaces.browser import MAX_RETRY_AFTER_MS, _retry_after_ms

    class _Response:
        def __init__(self, value: object) -> None:
            self.headers = {"retry-after": value} if value is not None else {}

    assert _retry_after_ms(_Response("30")) == 31_000
    # Missing or junk header falls back to the app's own window; guessing shorter would burn the
    # retry against a limit that has not reset.
    assert _retry_after_ms(_Response(None)) == 61_000
    assert _retry_after_ms(_Response("soon")) == 61_000
    # Capped, so a hostile or misconfigured header cannot park the sweep for an hour.
    assert _retry_after_ms(_Response("99999")) == MAX_RETRY_AFTER_MS


def test_signin_itself_recovers_from_a_restart() -> None:
    """A sign-in attempted while the app is restarting fails for a reason unrelated to
    credentials, and it costs an ENTIRE pass — every page after it measures the login screen.
    Observed live: one pass reported a login failure with four worker restarts around it. Page
    visits already recover; the sign-in that gates them must too, or recovery protects everything
    except the step that makes the rest meaningful."""
    import inspect

    from devteam_harness.surfaces import browser

    source = inspect.getsource(browser.BrowserSurface.use_viewport)
    assert "self._wait_for_recovery()" in source


def test_waiting_for_recovery_is_bounded() -> None:
    """An app that is genuinely down must not be waited on forever: converting a hard failure
    into a hang reads as 'still running', which is worse than a red result."""
    import inspect

    from devteam_harness.surfaces.browser import BrowserSurface as Surface

    signature = inspect.signature(Surface._wait_for_recovery)
    assert signature.parameters["attempts"].default > 0
    assert signature.parameters["interval_ms"].default > 0


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
