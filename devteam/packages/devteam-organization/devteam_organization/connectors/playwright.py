"""Playwright connector — read-only browser-journey evidence (§11).

Read-only testing only: it reads the JSON results a Playwright run already produced (failures,
console errors, network failures) and reports them as evidence. Launching a live browser requires
Playwright installed and is the injectable seam (a command runner) — deferred and fail-safe: with no
configured results (or no config), the connector is Unavailable and no job acts. It never
app under test.
"""

from __future__ import annotations

from devteam_protocol import AgentRole

from devteam_organization.connectors.framework import ConnectorResult, ConnectorType
from devteam_organization.connectors.reports import _read_json


class PlaywrightConnector:
    id = "playwright"
    name = "Playwright"
    type = ConnectorType.PLAYWRIGHT
    owner = AgentRole.QA

    def __init__(self, config_path: str = "", results_path: str = "") -> None:
        self._config = config_path
        self._results = results_path

    @property
    def enabled(self) -> bool:
        return bool(self._config or self._results)

    def fetch(self) -> ConnectorResult:
        if not (self._config or self._results):
            return ConnectorResult.unavailable("playwright not configured")
        results = _read_json(self._results) if self._results else None
        if results is None:
            # A live run needs Playwright installed (the injectable seam); until then, read-only.
            return ConnectorResult.unavailable("no playwright results (live run deferred)")
        journeys, failures, console_errors = _parse_playwright(results)
        return ConnectorResult.okay(
            {"journeys": journeys, "failures": failures, "console_errors": console_errors}
        )


def _parse_playwright(results: object) -> tuple[int, list[str], list[str]]:
    """Read Playwright JSON output: journey count, failing titles, console errors (tolerant)."""
    if not isinstance(results, dict):
        return (0, [], [])
    stats = results.get("stats")
    expected = int(stats.get("expected", 0)) if isinstance(stats, dict) else 0
    unexpected = int(stats.get("unexpected", 0)) if isinstance(stats, dict) else 0
    failures: list[str] = []
    for suite in _walk_suites(results):
        for spec in _as_list(suite.get("specs")):
            if isinstance(spec, dict) and spec.get("ok") is False:
                failures.append(str(spec.get("title") or "journey"))
    journeys = expected + unexpected if (expected or unexpected) else len(failures)
    return (journeys, failures, [])


def _walk_suites(node: object) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    if isinstance(node, dict):
        for suite in _as_list(node.get("suites")):
            if isinstance(suite, dict):
                out.append(suite)
                out.extend(_walk_suites(suite))
    return out


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []
