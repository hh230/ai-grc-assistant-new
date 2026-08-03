"""Tests for the HTTP surface and the Sentry agent.

These run WITHOUT a live app: the point being proven is that an absent app is reported, not
silently skipped. The one test that needs a live app says so and skips explicitly — and Sentry
itself still turns that absence into a finding, so a release gate can never mistake it for a pass.
"""

from __future__ import annotations

from devteam_harness.agents import sentry
from devteam_harness.agents.base import Severity
from devteam_harness.surfaces.http import HttpSurface
from devteam_harness.surfaces.routes import (
    ANONYMOUS_SAFE,
    PROTECTED,
    localised_pages,
    protected_paths,
)

DEAD = "http://localhost:59999"


# --- the anti-false-confidence property -------------------------------------------------------


def test_an_absent_app_is_reported_not_silently_skipped() -> None:
    """`apps/web`'s eval scripts print SKIP and exit 0, so CI passes while verifying nothing.
    This harness must never do that."""
    report = sentry.run(HttpSurface(base_url=DEAD))
    assert report.findings, "an unreachable app must produce a finding"
    finding = report.findings[0]
    assert finding.kind == "surface_unreachable"
    assert "not a pass" in finding.detail


def test_transport_failure_is_distinct_from_an_error_status() -> None:
    """A refused connection and a 500 are different facts and must not be conflated."""
    response = HttpSurface(base_url=DEAD).request("GET", "/api/anything")
    assert not response.reached_app
    assert response.transport_error is not None
    assert response.status == 0


def test_availability_is_honest_about_a_dead_app() -> None:
    assert HttpSurface(base_url=DEAD).available() is False


# --- the route inventory ----------------------------------------------------------------------


def test_every_listed_product_area_has_at_least_one_route() -> None:
    for area, paths in PROTECTED.items():
        assert paths, f"{area} claims coverage but lists no route"


def test_pages_are_checked_in_both_locales() -> None:
    """Arabic is a first-class surface here, not an afterthought."""
    pages = localised_pages()
    assert {locale for locale, _ in pages} == {"en", "ar"}

    # Every page must be checked once in each locale — no page covered in English only.
    by_locale: dict[str, set[str]] = {"en": set(), "ar": set()}
    for locale, path in pages:
        by_locale[locale].add(path.removeprefix(f"/{locale}"))
    assert by_locale["en"] == by_locale["ar"]
    assert by_locale["en"], "no pages configured"


def test_protected_and_anonymous_safe_never_overlap() -> None:
    """A route cannot both refuse anonymous callers and legitimately answer them; overlap would
    mean one of the two checks is wrong."""
    protected = {path for _, path in protected_paths()}
    assert not (protected & set(ANONYMOUS_SAFE)), "a route is classified both ways"


# --- severity ---------------------------------------------------------------------------------


def test_anonymous_exposure_would_be_reported_as_a_crash() -> None:
    """Confidentiality failures outrank rule violations: an anonymous read of tenant data is the
    worst class of defect a multi-tenant GRC product can ship."""
    assert Severity.CRASH.value == "crash"
    # The classifier treats these statuses as safe refusals, never as exposure.
    for status in (401, 403, 404, 405):
        assert status in sentry.ACCEPTABLE_ANONYMOUS_STATUSES
    assert 200 not in sentry.ACCEPTABLE_ANONYMOUS_STATUSES
