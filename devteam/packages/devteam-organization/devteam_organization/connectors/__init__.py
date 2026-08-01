"""AI Organization Connectors — a reusable, read-only integration layer (§11).

Jobs never integrate directly: they request a connector from the registry and ``fetch()``
evidence. Connectors are read-only, fail safely (an unavailable source is ``UNAVAILABLE``, never an
exception), and never fabricate. The registry owns caching, timing, metrics, and health — one fetch
path for every external system:

    Job → Connector → External System → Evidence → Mission
"""

from devteam_organization.connectors.config import (
    CADENCE_10_MIN,
    ConnectorConfig,
    Endpoint,
)
from devteam_organization.connectors.filesystem import FilesystemConnector
from devteam_organization.connectors.framework import (
    Connector,
    ConnectorCache,
    ConnectorHealth,
    ConnectorMetrics,
    ConnectorRegistry,
    ConnectorResult,
    ConnectorState,
    ConnectorStatus,
    ConnectorType,
)
from devteam_organization.connectors.github import GitHubConnector
from devteam_organization.connectors.playwright import PlaywrightConnector
from devteam_organization.connectors.reports import (
    ComplianceConnector,
    SecretsConnector,
    TestReportsConnector,
    VulnerabilityConnector,
)
from devteam_organization.connectors.runtime import RuntimeConnector
from devteam_organization.connectors.tls import TLSConnector
from devteam_organization.connectors.web import HttpSecurityConnector, WebsiteConnector
from devteam_organization.connectors.wiring import build_registry

__all__ = [
    "CADENCE_10_MIN",
    "ComplianceConnector",
    "Connector",
    "ConnectorCache",
    "ConnectorConfig",
    "ConnectorHealth",
    "ConnectorMetrics",
    "ConnectorRegistry",
    "ConnectorResult",
    "ConnectorState",
    "ConnectorStatus",
    "ConnectorType",
    "Endpoint",
    "FilesystemConnector",
    "GitHubConnector",
    "HttpSecurityConnector",
    "PlaywrightConnector",
    "RuntimeConnector",
    "SecretsConnector",
    "TLSConnector",
    "TestReportsConnector",
    "VulnerabilityConnector",
    "WebsiteConnector",
    "build_registry",
]
