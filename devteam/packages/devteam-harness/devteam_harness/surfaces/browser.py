"""The browser surface — drives a real Chromium against the running app.

This is the only surface that can see what a *user* sees. The HTTP surface proves an endpoint
answered; only a browser can prove the page actually rendered. That distinction is not academic
here: a Next.js `error.tsx` boundary returns **HTTP 200** while displaying "something went wrong",
so an HTTP-only sweep reports a healthy app on a page that is visibly broken. Every crash this
project shipped a fix for in the last week would have passed a status-code check.

**The sweep must be authenticated, and unauthenticated renders must be impossible to score as a
pass.** The first live run of this surface reported "48 pages healthy" — every one of which was
the *login page*, because the anonymous browser was redirected there and the login page renders
perfectly. That is the exact false confidence this harness exists to destroy, caught here only
because the result was checked instead of believed. `landed_on_login` is now a first-class
observation, and `is_healthy` is False whenever an authenticated sweep lands on it.

**Playwright is an optional dependency and its absence is a REPORTED finding, never a silent
skip** (see `pyproject.toml [project.optional-dependencies] browser`). `apps/web`'s existing eval
scripts print SKIP and exit 0 when their dependencies are missing, so CI passes while verifying
nothing.

On any failure it captures the four artifacts a human needs to reproduce without re-running
anything: **screenshot, console, network, and stack trace.**
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Self

DEFAULT_BASE_URL = "http://localhost:3000"
# Generous because the common target is a Next.js DEV server, where the first request to a route
# compiles it on demand and can take tens of seconds. Too tight a budget reports compile latency
# as a page defect — noise that trains people to ignore real findings.
DEFAULT_TIMEOUT_MS = 60_000

# The harness's own account, provisioned by `scripts/create-admin.mjs`. Overridable by env so a
# CI environment can point at its own seeded user; defaults are local-dev only and grant nothing
# outside a developer's machine.
HARNESS_EMAIL = os.environ.get("HARNESS_EMAIL", "harness@rasheed.local")
HARNESS_PASSWORD = os.environ.get("HARNESS_PASSWORD", "HarnessRun123!")

# Viewports checked. Mobile is a first-class surface: an RTL Arabic layout at 390px is where
# layout defects actually surface, and it is the width most GRC reviewers read on.
VIEWPORTS: dict[str, tuple[int, int]] = {
    "desktop": (1440, 900),
    "mobile": (390, 844),
}

# Text that means the app rendered its error boundary. Matched against the LIVE DOM, never the
# raw HTML: next-intl ships every translation into the page payload, so searching the HTML for an
# error string matches on EVERY page and reports a false crash everywhere. This was a real
# false positive; checking rendered text is the fix.
ERROR_BOUNDARY_MARKERS = (
    "Application error",
    "something went wrong",
    "حدث خطأ",
    "مشكلة غير متوقعة",
)

# Text that means we are looking at the login screen rather than the page we asked for.
LOGIN_MARKERS = ("Sign in to", "تسجيل الدخول")


def playwright_available() -> bool:
    """Whether a browser can actually be driven. Callers must report False, never hide it."""
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class PageObservation:
    """Everything one page visit produced — the evidence, separate from any judgement of it."""

    url: str
    locale: str
    viewport: str
    status: int = 0
    # Rendered text, not HTML. See ERROR_BOUNDARY_MARKERS.
    visible_text: str = ""
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)
    server_error_requests: list[str] = field(default_factory=list)
    screenshot_path: str | None = None
    transport_error: str | None = None
    # Whether this visit was made with a session. An authenticated visit that lands on the login
    # page proves nothing about the page we asked for and must never count as healthy.
    authenticated: bool = False
    # Set when the app went away and came back during this visit — a `next dev` worker restart,
    # not a defect in this page. Recorded rather than hidden: it is why a run has a gap.
    recovered_from_restart: bool = False

    @property
    def reached_app(self) -> bool:
        return self.transport_error is None

    @property
    def showed_error_boundary(self) -> bool:
        lowered = self.visible_text.lower()
        return any(marker.lower() in lowered for marker in ERROR_BOUNDARY_MARKERS)

    @property
    def landed_on_login(self) -> bool:
        return any(marker in self.visible_text for marker in LOGIN_MARKERS)

    @property
    def is_healthy(self) -> bool:
        return (
            self.reached_app
            and self.status < 500
            # A 404 on a page we claim to cover is not health — see `page_missing` in pilot.py.
            and self.status != 404
            and not self.showed_error_boundary
            and not self.page_errors
            and not self.server_error_requests
            # The guard the first live run needed: a logged-in sweep that shows the login screen
            # measured nothing, so it cannot be a pass.
            and not (self.authenticated and self.landed_on_login)
        )

    @property
    def needs_artifacts(self) -> bool:
        """Whether this visit produced anything a human would want evidence for.

        Deliberately WIDER than `is_healthy`. Console errors and failed requests do not make a
        page unhealthy — they are graded SUSPICIOUS, not CRASH — but they still generate findings,
        and a finding whose reproduce line points at artifacts that were never written is a dead
        end. Evidence follows the finding, not the verdict.
        """
        return not self.is_healthy or bool(self.console_errors) or bool(self.failed_requests)


@dataclass
class BrowserSurface:
    """A real Chromium pointed at the running app, capturing artifacts on every visit.

    Used as a context manager it keeps ONE browser and ONE logged-in context alive across the
    whole sweep. That is not just a speed concern: re-launching per page would drop the session
    cookie, and every protected page would silently become a login-page screenshot again.
    """

    base_url: str = DEFAULT_BASE_URL
    artifacts_dir: Path = field(default_factory=lambda: Path("artifacts"))
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    headless: bool = True
    email: str = HARNESS_EMAIL
    password: str = HARNESS_PASSWORD

    _playwright: Any = field(default=None, init=False, repr=False)
    _browser: Any = field(default=None, init=False, repr=False)
    _context: Any = field(default=None, init=False, repr=False)
    _authenticated: bool = field(default=False, init=False, repr=False)
    _viewport: str = field(default="desktop", init=False, repr=False)

    # --- lifecycle ----------------------------------------------------------------------------

    def __enter__(self) -> Self:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        for closeable in (self._context, self._browser):
            if closeable is not None:
                closeable.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._context = self._browser = self._playwright = None
        self._authenticated = False

    # --- session ------------------------------------------------------------------------------

    def use_viewport(self, viewport: str, *, locale: str = "en") -> None:
        """Switch viewport, re-logging-in because a new context has no cookies.

        Kept explicit rather than inferred per-visit so the cost (one login) is paid once per
        viewport instead of once per page.
        """
        if self._context is not None:
            self._context.close()
        width, height = VIEWPORTS[viewport]
        self._context = self._browser.new_context(
            viewport={"width": width, "height": height},
            locale="ar-SA" if locale == "ar" else "en-US",
        )
        self._viewport = viewport
        self._authenticated = self._login()

    def _login(self) -> bool:
        """Sign in through the real form. Returns whether a session was actually established.

        Waits on the login RESPONSE, not on the destination page. Waiting for the URL to change
        conflates "authentication failed" with "the dashboard was still compiling", and in Next.js
        dev mode the first compile of a route routinely outlives any sane timeout — which made
        three of four passes in the first live run report a false login failure.
        """
        page = self._context.new_page()
        try:
            page.goto(f"{self.base_url}/en/login", timeout=self.timeout_ms)
            page.wait_for_load_state("load", timeout=self.timeout_ms)
            page.fill("input[type=email], input[name=email]", self.email)
            page.fill("input[type=password], input[name=password]", self.password)
            with page.expect_response(
                lambda response: "/api/auth/login" in response.url,
                timeout=self.timeout_ms,
            ) as intercepted:
                page.click("button[type=submit]")
            return bool(intercepted.value.ok)
        except Exception:  # noqa: BLE001 — bad credentials, timeout, changed markup
            return False
        finally:
            page.close()

    @property
    def authenticated(self) -> bool:
        return self._authenticated

    # --- visiting -----------------------------------------------------------------------------

    def _load(self, page: Any, path: str, observation: PageObservation) -> None:
        """Navigate and record what came back. Transport failures land in the observation."""
        try:
            response = page.goto(f"{self.base_url}{path}", timeout=self.timeout_ms)
            observation.status = response.status if response is not None else 0
            # `networkidle` would hang on an app with a live SSE stream, which this one has
            # (mission pipeline). `load` plus a settle is what actually terminates.
            page.wait_for_load_state("load", timeout=self.timeout_ms)
            page.wait_for_timeout(600)
            observation.visible_text = _visible_text(page)
        except Exception as exc:  # noqa: BLE001 — timeouts, navigation, connection refused
            observation.transport_error = f"{type(exc).__name__}: {exc}"

    def _wait_for_recovery(self, *, attempts: int = 10, interval_ms: int = 3_000) -> bool:
        """Poll until the app answers again, or give up.

        Bounded on purpose: an app that is genuinely down must NOT be waited on forever, or the
        harness converts a hard failure into a hang — which reads as "still running" and is worse
        than a red result.
        """
        page = self._context.new_page()
        try:
            for _ in range(attempts):
                page.wait_for_timeout(interval_ms)
                try:
                    response = page.goto(f"{self.base_url}/en/login", timeout=self.timeout_ms)
                except Exception:  # noqa: BLE001, S112 — still down; polling IS the handling
                    continue
                if response is not None and response.status < 500:
                    return True
            return False
        finally:
            page.close()

    def visit(
        self,
        path: str,
        *,
        locale: str = "en",
        viewport: str | None = None,
        capture_always: bool = False,
    ) -> PageObservation:
        """Load one page and return what it produced.

        Artifacts are written only on failure by default — a passing sweep should not leave 48
        screenshots behind — but `capture_always` forces them when a human is reviewing a run.
        """
        if self._browser is None:
            # Standalone use (one page, no sweep): open and close a browser around this visit.
            with self as surface:
                surface.use_viewport(viewport or "desktop", locale=locale)
                return surface.visit(
                    path, locale=locale, viewport=viewport, capture_always=capture_always
                )
        if self._context is None:
            self.use_viewport(viewport or "desktop", locale=locale)

        observation = PageObservation(
            url=path,
            locale=locale,
            viewport=viewport or self._viewport,
            authenticated=self._authenticated,
        )
        page = self._context.new_page()
        page.on("console", lambda message: _record_console(observation, message))
        page.on("pageerror", lambda error: observation.page_errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda request: observation.failed_requests.append(
                f"{request.method} {request.url} — {request.failure}"
            ),
        )
        page.on("response", lambda response: _record_response(observation, response))

        try:
            try:
                self._load(page, path, observation)

                # A `next dev` worker that dies is respawned by its supervisor, and the app is
                # back within seconds. Without this, the FIRST such restart poisons every
                # remaining page in the sweep — which is exactly what a live run produced: one
                # crash, then a cascade of ERR_CONNECTION_REFUSED that said nothing about those
                # pages. The restart is still reported; it just stops eating the rest of the run.
                if not observation.reached_app and self._wait_for_recovery():
                    recovered = PageObservation(
                        url=path,
                        locale=locale,
                        viewport=observation.viewport,
                        authenticated=self._authenticated,
                        recovered_from_restart=True,
                    )
                    page.close()
                    # A restart drops the session cookie's server-side state; sign in again
                    # before retrying, or the retry measures the login page.
                    self._authenticated = self._login()
                    recovered.authenticated = self._authenticated
                    page = self._context.new_page()
                    page.on("pageerror", lambda error: recovered.page_errors.append(str(error)))
                    page.on("console", lambda message: _record_console(recovered, message))
                    page.on("response", lambda response: _record_response(recovered, response))
                    self._load(page, path, recovered)
                    observation = recovered
            except Exception as exc:  # noqa: BLE001 — timeouts, navigation, closed context
                observation.transport_error = f"{type(exc).__name__}: {exc}"

            if capture_always or observation.needs_artifacts:
                observation.screenshot_path = _capture(page, observation, self.artifacts_dir)
        finally:
            page.close()

        return observation


def _record_console(observation: PageObservation, message: Any) -> None:
    if message.type == "error":
        observation.console_errors.append(message.text)


def _record_response(observation: PageObservation, response: Any) -> None:
    if response.status >= 500:
        observation.server_error_requests.append(f"{response.status} {response.url}")


def _visible_text(page: Any) -> str:
    """Rendered text only.

    Reading `page.content()` and searching it for an error string matches on every page, because
    next-intl embeds all translations in the payload. That false positive is why this reads
    `innerText` from the live DOM instead.
    """
    try:
        return str(page.evaluate("() => document.body?.innerText ?? ''"))
    except Exception:  # noqa: BLE001 — a page that died mid-eval has no text to give
        return ""


def _capture(page: Any, observation: PageObservation, artifacts_dir: Path) -> str | None:
    """Write the four artifacts a human needs to reproduce this without re-running anything."""
    slug = (
        f"{observation.locale}_{observation.viewport}_"
        f"{observation.url.strip('/').replace('/', '_') or 'root'}"
    )
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    screenshot = artifacts_dir / f"{slug}.png"
    try:
        page.screenshot(path=str(screenshot), full_page=True)
    except Exception:  # noqa: BLE001 — a crashed page cannot be photographed; the rest still helps
        screenshot = artifacts_dir / f"{slug}.missing.png"

    # Console + network + stack traces travel WITH the screenshot: a picture of a broken page
    # without the stack trace behind it is a bug report nobody can act on.
    (artifacts_dir / f"{slug}.json").write_text(
        json.dumps(
            {
                "url": observation.url,
                "locale": observation.locale,
                "viewport": observation.viewport,
                "status": observation.status,
                "authenticated": observation.authenticated,
                "recovered_from_restart": observation.recovered_from_restart,
                "landed_on_login": observation.landed_on_login,
                "transport_error": observation.transport_error,
                "showed_error_boundary": observation.showed_error_boundary,
                "stack_traces": observation.page_errors,
                "console_errors": observation.console_errors,
                "failed_requests": observation.failed_requests,
                "server_error_requests": observation.server_error_requests,
                "visible_text_excerpt": observation.visible_text[:2000],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(screenshot) if screenshot.exists() else None
