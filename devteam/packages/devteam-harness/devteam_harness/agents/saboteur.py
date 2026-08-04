"""Saboteur — the Breaker's live-app arm: tries to break a RUNNING system on purpose.

The in-process Breaker attacks the Discovery engine with hostile values. That finds logic defects,
but it cannot find the class of bug that only exists once there is a server, a session, and a
browser: **races**. A double-submitted form, two tabs editing the same record, twenty requests
arriving at once — none of these are reachable from a single-threaded function call.

Four attacks, each aimed at a failure this product can actually suffer:

- **rapid_clicks** — a user double-clicking "Approve". In a GRC product a duplicated approval is
  not a cosmetic bug: it is a consequential action applied twice (CLAUDE.md §9 idempotency).
- **concurrent_requests** — the same endpoint hit N times at once. Looks for 5xx under
  concurrency, which usually means a connection pool, a transaction, or shared state giving way.
- **multiple_tabs** — two sessions of the same user in parallel, the thing every real user does
  and almost no test does.
- **hostile_payloads** — oversized, malformed, and injection-shaped bodies at the API edge, to
  confirm they are REJECTED (4xx) rather than crashing the server (5xx).

**Rejection is success.** A 400 or a 403 means the boundary held. This agent only reports when the
app crashes, leaks, or silently accepts something it should have refused — so a clean run here is
evidence, not absence of testing.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from devteam_harness.agents.base import AgentReport, Finding, Severity
from devteam_harness.surfaces.browser import BrowserSurface, PageObservation, playwright_available
from devteam_harness.surfaces.http import HttpSurface
from devteam_harness.surfaces.routes import PROTECTED

AGENT = "saboteur"

CONCURRENCY = 12

# Pages worth attacking through a browser: the ones with the most interactive surface, and the
# ones where a duplicated action would do real damage.
BROWSER_TARGETS: tuple[str, ...] = ("/dashboard", "/risk-register", "/plan")

# Bodies that must be refused at the boundary, never crash the process. Each is shaped like a real
# attack rather than random noise, so a rejection actually proves something.
HOSTILE_BODIES: tuple[tuple[str, object], ...] = (
    ("oversized_string", {"name": "A" * 200_000}),
    ("deep_nesting", {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": 1}}}}}}}}}),
    ("sql_injection", {"name": "'; DROP TABLE controls; --"}),
    ("template_injection", {"name": "{{7*7}}${7*7}<%= 7*7 %>"}),
    ("null_bytes", {"name": "before\u0000after"}),
    ("wrong_types", {"name": [1, 2, 3], "id": {"nested": True}}),
    ("empty_object", {}),
    # Not JSON at all — the parser must reject it rather than 500.
    ("not_json", "<xml>nope</xml>"),
)


@dataclass(frozen=True)
class Attempt:
    """One request's outcome, stripped to what the judgement needs."""

    status: int
    reached_app: bool


def run(surface: HttpSurface | None = None) -> AgentReport:
    """Attack a running app four ways. Reports only what actually broke."""
    report = AgentReport(agent=AGENT)
    surface = surface if surface is not None else HttpSurface()

    if not surface.available():
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="surface_unreachable",
                detail=(
                    f"no app answering at {surface.base_url} — the live attacks did NOT run. "
                    f"This is not a pass."
                ),
                reproduce=f"pnpm --filter @grc/web dev  # then re-run against {surface.base_url}",
            )
        )
        report.bump("unreachable")
        return report

    targets = [path for paths in PROTECTED.values() for path in paths][:6]

    _concurrent_reads(report, surface, targets)
    _rapid_repeat_submissions(report, surface)
    _hostile_payloads(report, surface)

    return report


def run_browser(surface: BrowserSurface, *, pages: tuple[str, ...] = BROWSER_TARGETS) -> AgentReport:
    """The two attacks that need a browser: the impatient user, and the multi-tab user.

    Kept separate from `run` because it needs Chromium and a session, and the release gate that
    runs on every PR has neither. Same rule as everywhere else: asking for this and not getting it
    is reported, not skipped.
    """
    report = AgentReport(agent=AGENT)

    if not playwright_available():
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind="browser_unavailable",
                detail=(
                    "playwright is not installed — the rapid-click and multi-tab attacks did NOT "
                    "run. This is not a pass."
                ),
                reproduce="uv sync --extra browser && uv run playwright install chromium",
            )
        )
        return report

    with surface:
        surface.use_viewport("desktop")
        if not surface.authenticated:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.SUSPICIOUS,
                    kind="login_failed",
                    detail="could not sign in — the browser attacks measured nothing",
                    reproduce="check the harness account exists (see README)",
                )
            )
            return report

        for path in pages:
            _judge_attack(report, surface.hammer(f"/en{path}"), "rapid_clicks")
            report.bump("pages_hammered")

            observations = surface.parallel_tabs(f"/en{path}")
            report.bump("tabs_opened", len(observations))
            for observation in observations:
                _judge_attack(report, observation, "multiple_tabs")

            # Tabs share a session, so they must agree. One tab rendering the app while another
            # shows the login screen means the session is not stable across concurrent use.
            reached = [o for o in observations if o.reached_app]
            if reached and len({o.landed_on_login for o in reached}) > 1:
                report.findings.append(
                    Finding(
                        agent=AGENT,
                        severity=Severity.CRASH,
                        kind="session_unstable_across_tabs",
                        detail=(
                            f"{path}: tabs sharing one session disagreed about whether the user "
                            f"is logged in"
                        ),
                        reproduce=f"open {path} in {len(observations)} tabs at once",
                    )
                )
            elif reached:
                report.bump("tabs_agreed")

    return report


def _judge_attack(report: AgentReport, observation: PageObservation, attack: str) -> None:
    """An attack succeeds when the app SURVIVES it. Only damage is reported."""
    if not observation.reached_app:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.SUSPICIOUS,
                kind=f"{attack}_unreachable",
                detail=f"{observation.url}: {observation.transport_error}",
                reproduce=observation.url,
            )
        )
        return

    for trace in observation.page_errors[:2]:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.CRASH,
                kind=f"{attack}_uncaught_exception",
                detail=f"{observation.url}: {trace.splitlines()[0]}",
                reproduce=observation.url,
            )
        )

    for failure in observation.server_error_requests[:2]:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.CRASH,
                kind=f"{attack}_5xx",
                detail=f"{observation.url}: {failure}",
                reproduce=observation.url,
            )
        )

    if observation.showed_error_boundary:
        report.findings.append(
            Finding(
                agent=AGENT,
                severity=Severity.CRASH,
                kind=f"{attack}_broke_the_page",
                detail=f"{observation.url}: the page fell back to its error boundary",
                reproduce=observation.url,
            )
        )

    if observation.is_healthy:
        report.bump(f"{attack}_survived")


def _concurrent_reads(report: AgentReport, surface: HttpSurface, targets: list[str]) -> None:
    """Hit each endpoint from many threads at once.

    A 401 from all twelve is a pass: the point is not to get in, it is to prove the app answers
    *consistently* under concurrency. Inconsistent statuses for identical simultaneous requests
    mean shared state is leaking between them — the seed of a cross-tenant bug.
    """
    for path in targets:
        attempts = _fire(surface.base_url + path, times=CONCURRENCY)
        report.bump("concurrent_requests", len(attempts))

        crashed = [a for a in attempts if a.reached_app and a.status >= 500]
        if crashed:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.CRASH,
                    kind="5xx_under_concurrency",
                    detail=(
                        f"{path}: {len(crashed)}/{len(attempts)} simultaneous requests returned "
                        f"5xx — the endpoint does not survive concurrent load"
                    ),
                    reproduce=f"seq {CONCURRENCY} | xargs -P{CONCURRENCY} -I_ curl -s -o /dev/null -w '%{{http_code}}\\n' {surface.base_url}{path}",
                )
            )
            continue

        statuses = {a.status for a in attempts if a.reached_app}
        if len(statuses) > 1:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.INVARIANT,
                    kind="inconsistent_under_concurrency",
                    detail=(
                        f"{path}: identical simultaneous requests answered differently "
                        f"({sorted(statuses)}) — state is leaking between requests"
                    ),
                    reproduce=f"fire {CONCURRENCY} parallel GETs at {path}",
                )
            )
        elif statuses:
            report.bump("consistent_under_concurrency")


def _rapid_repeat_submissions(report: AgentReport, surface: HttpSurface) -> None:
    """The double-click. Fire the same write twice, simultaneously.

    Aimed at the failure that matters most in a GRC product: a consequential action applied twice.
    Anonymous here, so the expected outcome is a clean rejection of BOTH — but a 5xx or a
    disagreement between the two proves the write path has no protection against a double submit,
    which is exactly what a logged-in user's impatient second click would exploit.
    """
    for path in ("/api/auth/login", "/api/risks", "/api/evidence"):
        attempts = _fire(
            surface.base_url + path,
            times=2,
            body={"idempotency_probe": True},
        )
        report.bump("double_submits", 1)

        if any(a.reached_app and a.status >= 500 for a in attempts):
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.CRASH,
                    kind="5xx_on_double_submit",
                    detail=f"{path}: a simultaneous double submit produced a 5xx",
                    reproduce=f"POST {path} twice in parallel",
                )
            )
        elif len({a.status for a in attempts if a.reached_app}) > 1:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.INVARIANT,
                    kind="double_submit_disagrees",
                    detail=(
                        f"{path}: two identical simultaneous writes were answered differently — "
                        f"the write path is order-dependent"
                    ),
                    reproduce=f"POST {path} twice in parallel",
                )
            )
        else:
            report.bump("double_submits_handled")


def _hostile_payloads(report: AgentReport, surface: HttpSurface) -> None:
    """Malformed and injection-shaped bodies must be REJECTED, not crash the server."""
    for name, body in HOSTILE_BODIES:
        response = _post_raw(surface.base_url + "/api/auth/login", body)
        report.bump("hostile_payloads_tried")

        if not response.reached_app:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.CRASH,
                    kind="payload_killed_the_connection",
                    detail=f"{name}: the server dropped the connection instead of rejecting it",
                    reproduce=f"POST /api/auth/login with the {name} payload",
                )
            )
        elif response.status >= 500:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.CRASH,
                    kind="5xx_on_hostile_payload",
                    detail=f"{name}: answered {response.status} — a bad request crashed the handler",
                    reproduce=f"POST /api/auth/login with the {name} payload",
                )
            )
        elif response.status < 400:
            report.findings.append(
                Finding(
                    agent=AGENT,
                    severity=Severity.CRASH,
                    kind="hostile_payload_accepted",
                    detail=f"{name}: answered {response.status} — the boundary ACCEPTED it",
                    reproduce=f"POST /api/auth/login with the {name} payload",
                )
            )
        else:
            report.bump("rejected_correctly")


def _fire(url: str, *, times: int, body: dict[str, object] | None = None) -> list[Attempt]:
    """Send `times` identical requests genuinely at once, and collect what came back."""
    with ThreadPoolExecutor(max_workers=times) as pool:
        return list(pool.map(lambda _: _request(url, body), range(times)))


def _request(url: str, body: dict[str, object] | None) -> Attempt:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return Attempt(status=response.status, reached_app=True)
    except urllib.error.HTTPError as exc:
        # A 4xx/5xx still reached the app — that is a result, not a transport failure.
        return Attempt(status=exc.code, reached_app=True)
    except Exception:  # noqa: BLE001 — refused, reset, timeout
        return Attempt(status=0, reached_app=False)


def _post_raw(url: str, body: object) -> Attempt:
    """Post a body that may deliberately not be JSON at all."""
    payload = body.encode() if isinstance(body, str) else json.dumps(body).encode()
    request = urllib.request.Request(url, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return Attempt(status=response.status, reached_app=True)
    except urllib.error.HTTPError as exc:
        return Attempt(status=exc.code, reached_app=True)
    except Exception:  # noqa: BLE001 — refused, reset, timeout
        return Attempt(status=0, reached_app=False)
