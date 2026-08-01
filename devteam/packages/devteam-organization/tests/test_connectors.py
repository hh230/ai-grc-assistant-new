"""The connector layer — framework (registry/cache/metrics/fail-safe), config, and connectors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from devteam_organization.connectors import (
    ConnectorCache,
    ConnectorConfig,
    ConnectorRegistry,
    ConnectorResult,
    ConnectorStatus,
    ConnectorType,
    Endpoint,
    GitHubConnector,
    TLSConnector,
    VulnerabilityConnector,
    WebsiteConnector,
)
from devteam_organization.connectors.filesystem import FilesystemConnector
from devteam_organization.connectors.probes import CertResult, HttpResult
from devteam_protocol import AgentRole


class _Stub:
    def __init__(
        self, cid: str, result: ConnectorResult | Exception, *, enabled: bool = True
    ) -> None:
        self.id = cid
        self.name = cid
        self.type = ConnectorType.WEBSITE
        self.owner = AgentRole.CISO
        self.enabled = enabled
        self._result = result
        self.calls = 0

    def fetch(self) -> ConnectorResult:
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_result_health_mapping() -> None:
    assert ConnectorResult.okay({}).health.value == "healthy"
    assert ConnectorResult.unavailable("x").health.value == "unavailable"
    assert ConnectorResult.errored("x").health.value == "warning"
    assert not ConnectorResult.unavailable("x").available


def test_registry_fetch_updates_state_and_metrics() -> None:
    registry = ConnectorRegistry(clock=lambda: 5.0)
    registry.register(_Stub("web", ConnectorResult.okay({"k": 1})))
    result = registry.fetch("web")
    assert result.ok
    state = registry.state("web")
    assert state is not None
    assert state.health.value == "healthy" and state.last_check == 5.0
    assert state.metrics.fetches == 1


def test_registry_guards_a_raising_connector() -> None:
    registry = ConnectorRegistry()
    registry.register(_Stub("bad", RuntimeError("boom")))
    result = registry.fetch("bad")  # must NOT raise
    assert result.status is ConnectorStatus.ERROR
    state = registry.state("bad")
    assert state is not None and state.metrics.failures == 1


def test_registry_disabled_and_unknown() -> None:
    registry = ConnectorRegistry()
    registry.register(_Stub("off", ConnectorResult.okay({}), enabled=False))
    assert registry.fetch("off").status is ConnectorStatus.DISABLED
    assert registry.fetch("missing").status is ConnectorStatus.UNAVAILABLE


def test_cache_serves_within_ttl_then_expires() -> None:
    clock = {"t": 100.0}
    registry = ConnectorRegistry(
        cache=ConnectorCache(ttl_seconds=50.0, clock=lambda: clock["t"]), clock=lambda: clock["t"]
    )
    stub = _Stub("c", ConnectorResult.okay({"n": 1}))
    registry.register(stub)
    registry.fetch("c")
    registry.fetch("c")  # within TTL → cache hit, connector not called again
    assert stub.calls == 1
    state = registry.state("c")
    assert state is not None and state.metrics.cache_hits == 1
    clock["t"] = 200.0  # past TTL
    registry.fetch("c")
    assert stub.calls == 2


def test_config_defaults_are_all_idle() -> None:
    config = ConnectorConfig.load(None)
    assert config.endpoints == () and config.github_repo == "" and config.vulnerability_report == ""


def test_config_loads_yaml_with_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_URL", "https://env.example.com")
    path = tmp_path / "org.yaml"
    path.write_text(
        "website:\n"
        "  endpoints:\n"
        "    - ${APP_URL}\n"
        "github:\n"
        "  owner: my-org\n"
        "  repo: ai-grc\n"
        "reports:\n"
        "  sarif: reports/results.sarif\n"
        "cadences:\n"
        "  overrides:\n"
        "    ciso.website_health: 30\n"
    )
    config = ConnectorConfig.load(path)
    assert config.endpoints[0].url == "https://env.example.com"  # ${APP_URL} substituted
    assert config.github_repo == "my-org/ai-grc"
    assert config.vulnerability_report == "reports/results.sarif"
    assert config.cadence_for("ciso.website_health", 600.0) == 30.0


def test_config_corrupt_file_is_safe(tmp_path: Path) -> None:
    path = tmp_path / "org.yaml"
    path.write_text("website: [unclosed")
    assert ConnectorConfig.load(path).endpoints == ()


def test_website_connector_unavailable_without_endpoints() -> None:
    connector = WebsiteConnector((), lambda u: HttpResult(u, True, 200, 5.0))
    assert connector.enabled is False
    assert connector.fetch().status is ConnectorStatus.UNAVAILABLE


def test_website_connector_reports_endpoints() -> None:
    endpoints = (Endpoint("app", "https://app"),)
    connector = WebsiteConnector(endpoints, lambda u: HttpResult(u, True, 200, 5.0))
    result = connector.fetch()
    assert result.ok
    rows = result.data["endpoints"]
    assert isinstance(rows, list) and rows[0]["ok"] is True


def test_tls_connector_unavailable_without_hosts() -> None:
    connector = TLSConnector((), lambda h: CertResult(h, True, 90, True))
    assert connector.fetch().status is ConnectorStatus.UNAVAILABLE


def test_github_connector_unavailable_without_repo() -> None:
    assert GitHubConnector(None).fetch().status is ConnectorStatus.UNAVAILABLE


def test_vulnerability_connector_reads_sarif(tmp_path: Path) -> None:
    absent = VulnerabilityConnector("")
    assert absent.fetch().status is ConnectorStatus.UNAVAILABLE
    sarif = tmp_path / "results.sarif"
    sarif.write_text(
        json.dumps({"runs": [{"results": [{"ruleId": "B105", "level": "error"}]}]})
    )
    result = VulnerabilityConnector(str(sarif)).fetch()
    assert result.ok
    high = result.data["high"]
    assert isinstance(high, list) and len(high) == 1  # the error-level SARIF result


def test_filesystem_connector_lists_read_only(tmp_path: Path) -> None:
    (tmp_path / "policy.md").write_text("x")
    connector = FilesystemConnector(("docs",), repo_root=tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "iso.md").write_text("y")
    result = connector.fetch()
    folders = result.data["folders"]
    assert isinstance(folders, list) and folders[0]["file_count"] == 1
    # Read-only: the connector never wrote anything — the dir still has exactly the one file.
    assert sorted(p.name for p in (tmp_path / "docs").iterdir()) == ["iso.md"]
