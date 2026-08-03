"""Pilot — flies a real browser through every page, in both locales and both viewports.

Sentry proves an endpoint *answered*. Pilot proves a page *rendered*. That gap is the whole
reason this agent exists: a Next.js `error.tsx` boundary returns **HTTP 200** while showing the
user "something went wrong", so a status-code sweep calls a visibly broken page healthy. Every
crash fixed in this app recently would have passed Sentry and failed Pilot.

It judges; it does not observe — `surfaces/browser.py` gathers the evidence, this decides what
counts as a defect. Keeping those apart means a disputed verdict can be re-argued against the
captured artifacts without re-running the browser.
"""

from __future__ import annotations

from pathlib import Path

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.surfaces.browser import BrowserSurface, PageObservation, playwright_available
from devteam_harness.surfaces.routes import LOCALES, PAGES

AGENT = "pilot"


def run(
    surface: BrowserSurface | None = None,
    *,
    pages: tuple[str, ...] = PAGES,
    viewports: tuple[str, ...] = ("desktop", "mobile"),
    artifacts_dir: Path | None = None,
) -> AgentReport:
    """Visit every page in every locale and viewport, reporting anything a user would call broken."""
    report = AgentReport(agent=AGENT)

    if not playwright_available():
        # Reported, never silently skipped — a gate must be able to refuse to call this a pass.
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="browser_unavailable",
                detail=(
                    "playwright is not installed — browser coverage did NOT run. This is not a "
                    "pass. Page rendering, console errors and mobile/RTL layout went unchecked."
                ),
                reproduce="uv sync --extra browser && uv run playwright install chromium",
            )
        )
        report.bump("unavailable")
        return report

    surface = surface or BrowserSurface(artifacts_dir=artifacts_dir or Path("artifacts"))

    with surface:
        for viewport in viewports:
            for locale in LOCALES:
                # One login per (viewport, locale) context — a fresh context has no cookies, and
                # sweeping protected pages without a session photographs the login page instead.
                surface.use_viewport(viewport, locale=locale)
                if not surface.authenticated:
                    report.findings.append(
                        Finding(
                            agent=AGENT,
                            severity=Severity.SUSPICIOUS,
                            kind="login_failed",
                            detail=(
                                f"[{locale}/{viewport}] could not sign in — every protected page "
                                f"in this pass would have measured the login screen, so this is "
                                f"not a pass."
                            ),
                            reproduce=(
                                "node apps/web/scripts/create-admin.mjs --email "
                                "harness@rasheed.local --password 'HarnessRun123!' "
                                "--name 'AI Test Harness' --org 'Harness Test Org'"
                            ),
                        )
                    )
                    report.bump("login_failures")
                    continue

                for page in pages:
                    observation = surface.visit(f"/{locale}{page}", locale=locale)
                    report.bump("visits")
                    _judge(report, observation)

    return report


def _judge(report: AgentReport, observation: PageObservation) -> None:
    """Turn one page visit into findings. Ordered most-severe-first, one finding per fact."""
    label = f"[{observation.locale}/{observation.viewport}] {observation.url}"
    reproduce = (
        f"open {observation.url} at {observation.viewport} width in {observation.locale}"
        + (f" — artifacts: {observation.screenshot_path}" if observation.screenshot_path else "")
    )

    # An app that went away and came back is an environment event, not a page defect — but it is
    # reported, because it explains a gap in the run and it is the mechanism behind the
    # intermittent "something went wrong" users see: a `next dev` worker dies under a burst of
    # first-compiles and its supervisor respawns it, failing whatever was in flight.
    if observation.recovered_from_restart:
        report.bump("restarts_survived")
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="app_restarted_mid_sweep",
                detail=(
                    f"{label}: the app stopped answering and came back — the server under test "
                    f"restarted during this run"
                ),
                reproduce=reproduce,
            )
        )

    if not observation.reached_app:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="page_unreachable",
                detail=f"{label}: {observation.transport_error}",
                reproduce=reproduce,
            )
        )
        return

    # The defect that made the FIRST live run of this agent report "48 pages healthy" — all 48
    # of which were the login page. A logged-in sweep that shows the login screen measured
    # nothing; scoring it as a pass is worse than reporting a failure, because it is a lie the
    # release gate would believe.
    if observation.authenticated and observation.landed_on_login:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="session_lost",
                detail=(
                    f"{label}: redirected to the login screen despite an authenticated session — "
                    f"this page went UNCHECKED, it did not pass"
                ),
                reproduce=reproduce,
            )
        )
        return

    # The defect a status check cannot see: HTTP 200 with an error boundary on screen.
    if observation.showed_error_boundary:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.CRASH,
                kind="error_boundary_rendered",
                detail=(
                    f"{label}: HTTP {observation.status} but the page displayed its error "
                    f"boundary — a status-code check would have called this healthy"
                ),
                reproduce=reproduce,
            )
        )

    if observation.status >= 500:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.CRASH,
                kind="page_5xx",
                detail=f"{label}: HTTP {observation.status}",
                reproduce=reproduce,
            )
        )

    # A page in the inventory that 404s means either the route was deleted or the harness is
    # claiming coverage it does not have. Both are defects; silently counting it as a pass is how
    # a sweep reports "21 pages healthy" while one of them does not exist. That happened.
    if observation.status == 404:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.INVARIANT,
                kind="page_missing",
                detail=(
                    f"{label}: HTTP 404 — this page is in the coverage inventory but the app "
                    f"does not serve it (route deleted, or the inventory is wrong)"
                ),
                reproduce=reproduce,
            )
        )

    # An uncaught exception is a defect even on a page that still looks fine — it means a code
    # path died silently, and silent death in a compliance product is how wrong data gets shown.
    for trace in observation.page_errors:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.CRASH,
                kind="uncaught_exception",
                detail=f"{label}: {trace.splitlines()[0]}",
                reproduce=reproduce,
            )
        )

    for failure in observation.server_error_requests:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.INVARIANT,
                kind="page_request_5xx",
                detail=f"{label}: {failure}",
                reproduce=reproduce,
            )
        )

    # Console errors are SUSPICIOUS, not CRASH: plenty are third-party noise, and grading them as
    # failures would train people to ignore the whole report.
    for message in observation.console_errors[:3]:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="console_error",
                detail=f"{label}: {message[:200]}",
                reproduce=reproduce,
            )
        )

    if observation.is_healthy:
        report.bump("healthy")
