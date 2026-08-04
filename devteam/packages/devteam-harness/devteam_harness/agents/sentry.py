"""Sentry — the Breaker's HTTP arm: attacks the running app over real HTTP.

Named for the role, not the error-tracking product. It answers one question a unit test cannot:
**does a live, fully-wired app leak anything to a caller who is not logged in?**

Its findings are severity CRASH rather than INVARIANT when data leaks, because an anonymous read
of tenant data is a confidentiality failure, not a rule violation — the worst class of defect a
multi-tenant GRC product can ship (CLAUDE.md §20).

ONE responsibility: does the app refuse an unauthenticated caller?

It used to ALSO sweep pages for 5xx. That was removed as redundant, measured rather than assumed:
anonymous page requests all return 307 (redirect to login) while protected routes return 401 — so
the page sweep re-measured the property the route sweep already covers, 24 requests at a time.
Whether a page RENDERS is Pilot's question, and Pilot asks it authenticated, which is the only way
the answer means anything.
"""

from __future__ import annotations

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.surfaces.http import HttpSurface
from devteam_harness.surfaces.routes import ANONYMOUS_SAFE, protected_paths

AGENT = "sentry"

# A protected endpoint may answer 401/403 (rejected), 404 (hidden), 3xx (redirect to login), or
# 405 (the method simply isn't exported — e.g. a PATCH-only route answering GET). None of these
# serve data. Treating 405 as a leak was a false positive the first sweep produced, and a harness
# that cries wolf trains people to ignore it.
ACCEPTABLE_ANONYMOUS_STATUSES = frozenset({401, 403, 404, 405})


def run(surface: HttpSurface | None = None) -> AgentReport:
    """Sweep every protected route anonymously and report anything that answers."""
    report = AgentReport(agent=AGENT)
    surface = surface if surface is not None else HttpSurface()

    if not surface.available():
        # Reported, never silently skipped — a gate must be able to refuse to call this a pass.
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="surface_unreachable",
                detail=(
                    f"no app answering at {surface.base_url} — HTTP coverage did NOT run. "
                    f"This is not a pass."
                ),
                reproduce=f"pnpm --filter @grc/web dev  # then re-run against {surface.base_url}",
            )
        )
        report.bump("unreachable")
        return report

    for area, path in protected_paths():
        report.bump("protected_routes_probed")
        response = surface.request("GET", path)

        if not response.reached_app:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.SUSPICIOUS,
                    kind="route_unreachable",
                    detail=f"{area}: {path} -> {response.transport_error}",
                    reproduce=f"curl -i {surface.base_url}{path}",
                )
            )
            continue

        if 300 <= response.status < 400 or response.status in ACCEPTABLE_ANONYMOUS_STATUSES:
            report.bump("correctly_refused")
            continue

        if response.status >= 500:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.CRASH,
                    kind="anonymous_request_5xx",
                    detail=f"{area}: {path} -> {response.status} (an anonymous caller crashed it)",
                    reproduce=f"curl -i {surface.base_url}{path}",
                )
            )
            continue

        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.CRASH,
                kind="anonymous_data_exposure",
                detail=(
                    f"{area}: {path} -> {response.status} to an anonymous caller "
                    f"({len(response.body)} bytes)"
                ),
                reproduce=f"curl -i {surface.base_url}{path}",
            )
        )

    # Endpoints that may answer anonymously: the body, not the status, is the security control.
    for path, spec in ANONYMOUS_SAFE.items():
        report.bump("anonymous_safe_probed")
        response = surface.request("GET", path)
        if not response.reached_app:
            continue
        payload = response.json()
        if not isinstance(payload, dict):
            continue
        for key in spec.forbidden_when_anonymous:
            if payload.get(key) is not None:
                report.findings.append(
                    Finding(
                        agent=AGENT,
                        severity=Severity.CRASH,
                        kind="identity_leaked_to_anonymous",
                        detail=f"{spec.area}: {path} returned a non-null {key!r} with no session",
                        reproduce=f"curl -i {surface.base_url}{path}",
                    )
                )
            else:
                report.bump("anonymous_identity_withheld")

    return report
