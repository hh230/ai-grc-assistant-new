"""Tests for the Saboteur — the Breaker's live-app arm.

These run WITHOUT an app or a browser. What needs a live system is proven by the recorded live
run; what is tested here is the judgement, which is where an attack agent goes wrong: by calling
a correct rejection a defect, or by calling a real failure noise.
"""

from __future__ import annotations

from devteam_harness.agents import saboteur
from devteam_harness.agents.base import AgentReport, Severity
from devteam_harness.surfaces.browser import PageObservation
from devteam_harness.surfaces.http import HttpSurface

DEAD = "http://localhost:59998"


# --- the anti-false-confidence property -------------------------------------------------------


def test_an_absent_app_is_reported_not_silently_skipped() -> None:
    report = saboteur.run(HttpSurface(base_url=DEAD))
    assert report.findings[0].kind == "surface_unreachable"
    assert "not a pass" in report.findings[0].detail


def test_a_missing_browser_is_reported_not_silently_skipped(monkeypatch: object) -> None:
    monkeypatch.setattr(saboteur, "playwright_available", lambda: False)  # type: ignore[attr-defined]
    report = saboteur.run_browser(None)  # type: ignore[arg-type]
    assert report.findings[0].kind == "browser_unavailable"
    assert "not a pass" in report.findings[0].detail


# --- rejection is success ---------------------------------------------------------------------


def test_surviving_an_attack_produces_no_finding() -> None:
    """A 400 means the boundary held. An attack agent that reports every rejection as a defect is
    worse than useless — it buries the one attack that actually landed."""
    survived = PageObservation(
        url="/en/dashboard (hammered x8)", locale="en", viewport="desktop", status=200,
        visible_text="Dashboard", authenticated=True,
    )
    report = AgentReport(agent=saboteur.AGENT)
    saboteur._judge_attack(report, survived, "rapid_clicks")
    assert not report.findings
    assert report.stats["rapid_clicks_survived"] == 1


def test_an_exception_under_rapid_clicks_is_a_crash() -> None:
    """The impatient user. A duplicated consequential action is the failure that matters most in
    a GRC product (CLAUDE.md 9)."""
    broke = PageObservation(
        url="/en/plan (hammered x8)", locale="en", viewport="desktop", status=200,
        visible_text="Plan", authenticated=True,
        page_errors=["TypeError: cannot read approve of undefined"],
    )
    report = AgentReport(agent=saboteur.AGENT)
    saboteur._judge_attack(report, broke, "rapid_clicks")
    assert report.findings[0].kind == "rapid_clicks_uncaught_exception"
    assert report.findings[0].severity is Severity.CRASH


def test_an_error_boundary_under_attack_is_a_crash() -> None:
    broke = PageObservation(
        url="/en/risk-register (tab 2/4)", locale="en", viewport="desktop", status=200,
        visible_text="Something went wrong", authenticated=True,
    )
    report = AgentReport(agent=saboteur.AGENT)
    saboteur._judge_attack(report, broke, "multiple_tabs")
    assert "multiple_tabs_broke_the_page" in {f.kind for f in report.findings}


# --- the payload table ------------------------------------------------------------------------


def test_hostile_payloads_cover_the_shapes_that_actually_break_parsers() -> None:
    names = {name for name, _ in saboteur.HOSTILE_BODIES}
    assert {"oversized_string", "sql_injection", "wrong_types", "not_json"} <= names


def test_one_payload_is_not_json_at_all() -> None:
    """A JSON parser must reject a non-JSON body, not 500 on it. Every payload being valid JSON
    would leave the parser itself untested."""
    bodies = dict(saboteur.HOSTILE_BODIES)
    assert isinstance(bodies["not_json"], str)


def test_the_oversized_payload_is_actually_oversized() -> None:
    bodies = dict(saboteur.HOSTILE_BODIES)
    assert len(str(bodies["oversized_string"])) > 100_000


# --- concurrency ------------------------------------------------------------------------------


def test_concurrency_is_high_enough_to_race() -> None:
    """Two requests rarely collide; a dozen do. Too low a number turns this into a slow way of
    making the same request twice."""
    assert saboteur.CONCURRENCY >= 8


def test_browser_targets_are_pages_where_a_duplicate_action_would_hurt() -> None:
    assert "/plan" in saboteur.BROWSER_TARGETS
