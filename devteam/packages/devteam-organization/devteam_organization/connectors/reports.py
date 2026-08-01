"""Report connectors — read reports the project ALREADY produces; never run tools, never fabricate.

Test Reports (JUnit/pytest/coverage/regression), Vulnerability (SARIF/JSON/CSV), Secrets, and
Compliance. Each reads a configured file if it exists; an absent/unparseable report is Unavailable —
so a job only ever acts on findings that really exist in a real report.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from xml.etree import ElementTree

from devteam_protocol import AgentRole

from devteam_organization.connectors.framework import ConnectorResult, ConnectorType


def _read_text(path: str) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return p.read_text()
    except OSError:
        return None


def _read_json(path: str) -> object | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data


class TestReportsConnector:
    id = "test_reports"
    name = "Test Reports"
    type = ConnectorType.TEST_REPORTS
    owner = AgentRole.QA

    def __init__(
        self, *, junit: str = "", pytest_json: str = "", regression: str = "", coverage: str = ""
    ) -> None:
        self._junit = junit
        self._pytest = pytest_json
        self._regression = regression
        self._coverage = coverage

    @property
    def enabled(self) -> bool:
        return any((self._junit, self._pytest, self._regression, self._coverage))

    def fetch(self) -> ConnectorResult:
        failing: list[str] = []
        total = 0
        sources: list[str] = []

        junit_text = _read_text(self._junit)
        if junit_text is not None:
            names, count = _parse_junit(junit_text)
            failing.extend(names)
            total += count
            sources.append("junit")

        for kind, path in (("pytest", self._pytest), ("regression", self._regression)):
            report = _read_json(path)
            if report is not None:
                names = _failing_tests(report)
                failing.extend(names)
                total += len(names)
                sources.append(kind)

        coverage = _coverage_percent(_read_json(self._coverage))
        if coverage is not None:
            sources.append("coverage")

        if not sources:
            return ConnectorResult.unavailable("no test reports available")
        return ConnectorResult.okay(
            {"failing": failing, "total": total, "coverage_percent": coverage, "sources": sources}
        )


class VulnerabilityConnector:
    id = "vulnerability"
    name = "Vulnerability Reports"
    type = ConnectorType.VULNERABILITY
    owner = AgentRole.CISO

    def __init__(self, report_path: str = "") -> None:
        self._path = report_path

    @property
    def enabled(self) -> bool:
        return bool(self._path)

    def fetch(self) -> ConnectorResult:
        vulns = _read_vulnerabilities(self._path)
        if vulns is None:
            return ConnectorResult.unavailable("no vulnerability report available")
        high = [v for v in vulns if v["severity"] in ("high", "critical", "error")]
        return ConnectorResult.okay({"all": vulns, "high": high, "count": len(vulns)})


class SecretsConnector:
    id = "secrets"
    name = "Secret Scan Reports"
    type = ConnectorType.SECRETS
    owner = AgentRole.CISO

    def __init__(self, report_path: str = "") -> None:
        self._path = report_path

    @property
    def enabled(self) -> bool:
        return bool(self._path)

    def fetch(self) -> ConnectorResult:
        report = _read_json(self._path)
        if report is None:
            return ConnectorResult.unavailable("no secret-scan report available")
        findings = _secret_findings(report)
        return ConnectorResult.okay({"findings": findings, "count": len(findings)})


class ComplianceConnector:
    id = "compliance"
    name = "Compliance"
    type = ConnectorType.COMPLIANCE
    owner = AgentRole.GRC_EXPERT

    def __init__(self, report_path: str = "") -> None:
        self._path = report_path

    @property
    def enabled(self) -> bool:
        return bool(self._path)

    def fetch(self) -> ConnectorResult:
        report = _read_json(self._path)
        if report is None:
            return ConnectorResult.unavailable("no compliance report available")
        gaps = _compliance_gaps(report)
        return ConnectorResult.okay({"gaps": gaps, "count": len(gaps)})


# --- tolerant parsers (real reports only; never invent entries) --------------------------------


def _parse_junit(text: str) -> tuple[list[str], int]:
    try:
        root = ElementTree.fromstring(text)  # noqa: S314 - project's own CI report, not untrusted
    except ElementTree.ParseError:
        return ([], 0)
    cases = root.iter("testcase")
    failing: list[str] = []
    total = 0
    for case in cases:
        total += 1
        if case.find("failure") is not None or case.find("error") is not None:
            failing.append(case.get("name") or "test")
    return (failing, total)


def _failing_tests(report: object) -> list[str]:
    out: list[str] = []
    for item in _entries(report, ("tests", "results", "failures", "cases")):
        if isinstance(item, dict):
            status = str(item.get("status") or item.get("outcome") or "").lower()
            if status in ("failed", "failure", "flaky", "error", "errored"):
                out.append(str(item.get("name") or item.get("id") or "test"))
        elif isinstance(item, str):
            out.append(item)
    return out


def _coverage_percent(report: object) -> float | None:
    if isinstance(report, dict):
        totals = report.get("totals")
        if isinstance(totals, dict) and isinstance(totals.get("percent_covered"), (int, float)):
            return float(totals["percent_covered"])
        if isinstance(report.get("percent_covered"), (int, float)):
            return float(report["percent_covered"])
    return None


def _read_vulnerabilities(path: str) -> list[dict[str, str]] | None:
    if not path:
        return None
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return _vulns_csv(path)
    report = _read_json(path)
    if report is None:
        return None
    if isinstance(report, dict) and "runs" in report:  # SARIF
        return _vulns_sarif(report)
    return _vulns_json(report)


def _vulns_json(report: object) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in _entries(report, ("vulnerabilities", "dependencies", "advisories")):
        if isinstance(item, dict):
            severity = str(item.get("severity") or item.get("cvss_severity") or "unknown").lower()
            package = str(item.get("package") or item.get("name") or item.get("id") or "dependency")
            out.append({"package": package, "severity": severity})
    return out


def _vulns_sarif(report: object) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(report, dict):
        return out
    for run in _as_list(report.get("runs")):
        if not isinstance(run, dict):
            continue
        for result in _as_list(run.get("results")):
            if isinstance(result, dict):
                level = str(result.get("level") or "warning").lower()
                rule = str(result.get("ruleId") or "finding")
                out.append({"package": rule, "severity": level})
    return out


def _vulns_csv(path: str) -> list[dict[str, str]] | None:
    text = _read_text(path)
    if text is None:
        return None
    out: list[dict[str, str]] = []
    for row in csv.DictReader(text.splitlines()):
        lowered = {k.lower(): v for k, v in row.items() if k}
        severity = str(lowered.get("severity") or "unknown").lower()
        package = str(lowered.get("package") or lowered.get("name") or lowered.get("id") or "dep")
        out.append({"package": package, "severity": severity})
    return out


def _secret_findings(report: object) -> list[str]:
    out: list[str] = []
    entries = _entries(report, ("findings", "results", "leaks", "secrets"))
    for item in entries:
        if isinstance(item, dict):
            label = item.get("description") or item.get("ruleId") or item.get("rule") or "secret"
            out.append(str(label))
        elif isinstance(item, str):
            out.append(item)
    return out


def _compliance_gaps(report: object) -> list[str]:
    out: list[str] = []
    if isinstance(report, dict):
        for gap in _as_list(report.get("gaps")):
            out.append(str(gap if isinstance(gap, str) else _label(gap)))
        for control in _as_list(report.get("controls")):
            status = str(control.get("status", "")).lower() if isinstance(control, dict) else ""
            if status in ("gap", "failed", "open"):
                out.append(f"control {_label(control)}")
        for evidence in _as_list(report.get("evidence")):
            if isinstance(evidence, dict) and evidence.get("fresh") is False:
                out.append(f"stale evidence {_label(evidence)}")
    elif isinstance(report, list):
        out.extend(str(x) for x in report)
    return out


def _entries(report: object, keys: tuple[str, ...]) -> list[object]:
    if isinstance(report, list):
        return list(report)
    if isinstance(report, dict):
        for key in keys:
            value = report.get(key)
            if isinstance(value, list):
                return list(value)
    return []


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _label(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("id") or item.get("name") or "item")
    return str(item)
