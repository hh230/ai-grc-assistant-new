"""The route inventory the HTTP surface exercises, grouped by the product area each belongs to.

Kept as data rather than discovered from the filesystem so a route that DISAPPEARS is as visible
as one that breaks: if someone deletes an endpoint, the sweep reports it missing instead of
silently testing one fewer thing.

`PROTECTED` is the security-critical set: every one of these must refuse an unauthenticated
caller. `PUBLIC` is the small set that legitimately answers anyone.
"""

from __future__ import annotations

from dataclasses import dataclass

# area -> paths. Areas mirror the product surfaces a release gate cares about.
PROTECTED: dict[str, tuple[str, ...]] = {
    "dashboard": ("/api/dashboard/export?range=90", "/api/governance/coverage"),
    "risk_register": ("/api/risks",),
    "documents": ("/api/documents", "/api/analyses", "/api/analyses/usage"),
    "evidence": ("/api/evidence",),
    "policies": ("/api/policies",),
    "frameworks": ("/api/controls",),
    "notifications": ("/api/knowledge-worker/events",),
    # NOTE: /api/account/profile exports only PATCH, so an anonymous GET answers 405 — correct
    # behaviour, not a leak. /api/auth/session is deliberately anonymous-safe and lives in
    # ANONYMOUS_SAFE below, where its *body* is checked instead of its status.
    "user_management": ("/api/account/profile",),
    "organizations": ("/api/organizations",),
    "reports": ("/api/reports",),
    "access_requests": ("/api/access-requests",),
    "missions": ("/api/missions",),
    "governance_plan": (
        "/api/governance-plans/active",
        "/api/governance-plans/versions",
        "/api/governance-plans/maturity",
    ),
    "discovery": ("/api/discovery/sessions/active",),
    "conversations": ("/api/conversations",),
}

# Endpoints that must stay reachable without a session — breaking these locks everyone out.
PUBLIC: dict[str, tuple[str, ...]] = {
    "auth": ("/api/auth/login", "/api/auth/forgot-password"),
}

# Endpoints that legitimately ANSWER an anonymous caller, where the risk is not the status code
# but the body. Checking the status alone would call these leaks (a false positive); checking the
# body is the test that actually means something — the endpoint must reveal no identity.
# `forbidden_when_anonymous` are JSON paths that must be null/absent without a session.
@dataclass(frozen=True)
class AnonymousSafeRoute:
    area: str
    # JSON keys that must be null/absent without a session.
    forbidden_when_anonymous: tuple[str, ...]


ANONYMOUS_SAFE: dict[str, AnonymousSafeRoute] = {
    # The client uses this to discover whether it is logged in, so 200 + {"user": null} is
    # correct. A populated `user` for an anonymous caller would be a session leak.
    "/api/auth/session": AnonymousSafeRoute(
        area="user_management", forbidden_when_anonymous=("user",)
    ),
}

# Localised pages, checked in both locales and both viewports by the browser surface later.
PAGES: tuple[str, ...] = (
    "/dashboard",
    "/risk-register",
    "/documents",
    "/evidence",
    "/policies",
    "/frameworks",
    "/reports",
    "/settings",
    "/missions",
    "/discovery",
    "/plan",
    "/help",
)

LOCALES: tuple[str, ...] = ("en", "ar")


def protected_paths() -> list[tuple[str, str]]:
    """(area, path) for every endpoint that must reject an anonymous caller."""
    return [(area, path) for area, paths in PROTECTED.items() for path in paths]


def localised_pages() -> list[tuple[str, str]]:
    """(locale, path) for every page in both locales — Arabic is a first-class surface here,
    not an afterthought checked only when someone remembers."""
    return [(locale, f"/{locale}{page}") for locale in LOCALES for page in PAGES]
