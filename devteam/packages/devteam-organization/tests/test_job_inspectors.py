"""The twelve jobs — evidence comes ONLY from connectors; a Mission opens only on real evidence."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from devteam_organization.connectors import (
    ConnectorRegistry,
    ConnectorResult,
    ConnectorType,
)
from devteam_organization.jobs.agent_jobs import (
    CEOJob,
    CTOJob,
    DevTeamJob,
    GRCExpertJob,
    QAJob,
    SupervisorJob,
)
from devteam_organization.jobs.ciso_jobs import (
    DependencySecurityJob,
    RuntimeHealthJob,
    SecretExposureJob,
    SecurityHeadersJob,
    TlsCertificateJob,
    WebsiteHealthJob,
)
from devteam_organization.jobs.framework import JobContext, JobHealth, Schedule
from devteam_protocol import AgentRole

_S = Schedule(600.0)


def _ctx() -> JobContext:
    return JobContext(now=1000.0, repo_root=Path("."))


class _FakeConnector:
    """A connector returning a canned result — registered in the REAL registry the job fetches."""

    def __init__(self, cid: str, result: ConnectorResult, *, ctype: ConnectorType) -> None:
        self.id = cid
        self.name = cid
        self.type = ctype
        self.owner = AgentRole.CISO
        self.enabled = True
        self._result = result

    def fetch(self) -> ConnectorResult:
        return self._result


def _registry(
    cid: str, result: ConnectorResult, ctype: ConnectorType = ConnectorType.WEBSITE
) -> ConnectorRegistry:
    registry = ConnectorRegistry()
    registry.register(_FakeConnector(cid, result, ctype=ctype))
    return registry


def _ok(data: Mapping[str, object]) -> ConnectorResult:
    return ConnectorResult.okay(data)


# --- CISO ------------------------------------------------------------------------------------


def test_website_unavailable_connector_opens_no_mission() -> None:
    registry = _registry("website", ConnectorResult.unavailable("down"))
    job = WebsiteHealthJob(registry, schedule=_S, failure_threshold=1)
    assert job.inspect(_ctx()).mission_request is None


def test_website_opens_mission_when_endpoint_is_down() -> None:
    data = {"endpoints": [{"name": "app", "url": "u", "ok": False}]}
    job = WebsiteHealthJob(_registry("website", _ok(data)), schedule=_S, failure_threshold=1)
    result = job.inspect(_ctx())
    assert result.health is JobHealth.DEGRADED and result.mission_request is not None


def test_security_headers_flags_missing() -> None:
    good = {"endpoints": [{"name": "app", "url": "u", "reachable": True, "missing": []}]}
    ok = SecurityHeadersJob(_registry("http_security", _ok(good)), schedule=_S)
    assert ok.inspect(_ctx()).mission_request is None
    bad = {"endpoints": [{"name": "app", "url": "u", "reachable": True, "missing": ["CSP"]}]}
    job = SecurityHeadersJob(_registry("http_security", _ok(bad)), schedule=_S)
    assert job.inspect(_ctx()).mission_request is not None


def test_tls_flags_near_expiry() -> None:
    ok_data = {"hosts": [{"host": "h", "hostname_valid": True, "days_to_expiry": 90}]}
    ok = TlsCertificateJob(_registry("tls", _ok(ok_data)), schedule=_S, warn_days=21)
    assert ok.inspect(_ctx()).mission_request is None
    soon = {"hosts": [{"host": "h", "hostname_valid": True, "days_to_expiry": 5}]}
    job = TlsCertificateJob(_registry("tls", _ok(soon)), schedule=_S, warn_days=21)
    assert job.inspect(_ctx()).mission_request is not None


def test_dependency_opens_mission_on_high_vuln() -> None:
    empty = DependencySecurityJob(
        _registry("vulnerability", ConnectorResult.unavailable("no report")),
        schedule=_S,
    )
    assert empty.inspect(_ctx()).mission_request is None
    data = {"high": [{"package": "lodash", "severity": "high"}]}
    job = DependencySecurityJob(_registry("vulnerability", _ok(data)), schedule=_S)
    assert job.inspect(_ctx()).mission_request is not None


def test_secret_opens_mission_on_finding() -> None:
    data = {"findings": ["AWS key committed"]}
    job = SecretExposureJob(_registry("secrets", _ok(data)), schedule=_S)
    assert job.inspect(_ctx()).mission_request is not None


def test_runtime_health_escalates_a_down_worker() -> None:
    up = RuntimeHealthJob(_registry("runtime", _ok({"workers_down": []})), schedule=_S)
    assert up.inspect(_ctx()).mission_request is None
    data = {"workers_down": ["com.rasheed.devteam-organization"]}
    job = RuntimeHealthJob(_registry("runtime", _ok(data)), schedule=_S)
    result = job.inspect(_ctx())
    assert result.mission_request is not None and result.mission_request.escalate


# --- CTO / QA / GRC / DevTeam / CEO / Supervisor ---------------------------------------------


def test_cto_opens_mission_on_ci_signal() -> None:
    idle = CTOJob(_registry("github", ConnectorResult.unavailable("no repo")), schedule=_S)
    assert idle.inspect(_ctx()).mission_request is None
    data = {"latest_failure": {"summary": "CI failure", "head_branch": "develop"}, "open_prs": []}
    job = CTOJob(_registry("github", _ok(data)), schedule=_S)
    assert job.inspect(_ctx()).mission_request is not None


def test_qa_opens_mission_on_failing_tests() -> None:
    data = {"failing": ["test_login"], "total": 10}
    job = QAJob(_registry("test_reports", _ok(data)), schedule=_S)
    assert job.inspect(_ctx()).mission_request is not None


def test_grc_opens_mission_on_gap() -> None:
    data = {"gaps": ["control A.5.1"]}
    job = GRCExpertJob(_registry("compliance", _ok(data)), schedule=_S)
    assert job.inspect(_ctx()).mission_request is not None


def test_devteam_surfaces_gated_work_without_fabricating() -> None:
    data = {"awaiting_missions": ["m1"]}
    job = DevTeamJob(_registry("runtime", _ok(data)), schedule=_S)
    result = job.inspect(_ctx())
    assert result.health is JobHealth.DEGRADED and result.mission_request is None


def test_ceo_escalates_only_past_thresholds() -> None:
    calm = CEOJob(
        _registry("runtime", _ok({"open_missions": 1, "incidents": 0})),
        schedule=_S,
        open_missions_threshold=10,
        incident_threshold=1,
    )
    assert calm.inspect(_ctx()).mission_request is None
    busy = CEOJob(
        _registry("runtime", _ok({"open_missions": 11, "incidents": 0})),
        schedule=_S,
        open_missions_threshold=10,
        incident_threshold=1,
    )
    result = busy.inspect(_ctx())
    assert result.mission_request is not None and result.mission_request.escalate


def test_supervisor_escalates_a_down_worker() -> None:
    tick = Schedule(0.0, every_tick=True)
    up = SupervisorJob(_registry("runtime", _ok({"workers_down": []})), schedule=tick)
    assert up.inspect(_ctx()).mission_request is None
    down = SupervisorJob(
        _registry("runtime", _ok({"workers_down": ["w"]})), schedule=tick
    )
    assert down.inspect(_ctx()).mission_request is not None
