"""Compose the connector registry — the one place connectors are built and registered (§11).

Builds every connector from the single ``ConnectorConfig`` (empty sources ⇒ disabled/Unavailable
connectors) and registers them in a ``ConnectorRegistry`` with the configured cache TTL. Jobs fetch
through this registry; they never see these constructors.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from devteam_github import GitHubActions
from devteam_observability import RuntimeStateView

from devteam_organization.connectors.config import ConnectorConfig
from devteam_organization.connectors.filesystem import FilesystemConnector
from devteam_organization.connectors.framework import ConnectorCache, ConnectorRegistry
from devteam_organization.connectors.github import GitHubConnector
from devteam_organization.connectors.playwright import PlaywrightConnector
from devteam_organization.connectors.probes import (
    CertProbe,
    HttpProbe,
    WorkerProbe,
    WorkerStatus,
    make_cert_probe,
    make_http_probe,
    make_launchctl_worker_probe,
)
from devteam_organization.connectors.reports import (
    ComplianceConnector,
    SecretsConnector,
    TestReportsConnector,
    VulnerabilityConnector,
)
from devteam_organization.connectors.runtime import RuntimeConnector
from devteam_organization.connectors.tls import TLSConnector
from devteam_organization.connectors.web import HttpSecurityConnector, WebsiteConnector


def build_registry(
    config: ConnectorConfig,
    *,
    view_provider: Callable[[], RuntimeStateView | None] | None = None,
    github: GitHubActions | None = None,
    repo_root: str = ".",
    http_probe: HttpProbe | None = None,
    cert_probe: CertProbe | None = None,
    worker_probe: WorkerProbe | None = None,
    clock: Callable[[], float] = time.time,
) -> ConnectorRegistry:
    """Every connector, wired from the config. The runtime connector watches the LaunchAgents
    named in the config; GitHub is injected (built from the config repo + env token)."""
    http = http_probe or make_http_probe()
    cert = cert_probe or make_cert_probe()
    labels = config.runtime_workers
    workers = worker_probe or (
        make_launchctl_worker_probe(labels) if labels else _no_workers
    )
    registry = ConnectorRegistry(
        cache=ConnectorCache(ttl_seconds=config.cache_ttl_seconds, clock=clock), clock=clock
    )
    for connector in (
        WebsiteConnector(config.endpoints, http, slow_ms=config.response_time_warn_ms),
        HttpSecurityConnector(config.endpoints, http),
        TLSConnector(config.tls_hosts, cert),
        GitHubConnector(github),
        RuntimeConnector(workers, view_provider, clock=clock),
        TestReportsConnector(
            junit=config.junit_report,
            pytest_json=config.pytest_report,
            regression=config.regression_report,
            coverage=config.coverage_report,
        ),
        VulnerabilityConnector(config.vulnerability_report),
        SecretsConnector(config.secret_report),
        ComplianceConnector(config.compliance_report),
        FilesystemConnector(config.filesystem_folders, repo_root=repo_root),
        PlaywrightConnector(config.playwright_config),
    ):
        registry.register(connector)
    return registry


def _no_workers() -> Sequence[WorkerStatus]:
    return ()
