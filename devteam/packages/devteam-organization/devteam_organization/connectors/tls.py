"""TLS connector — read-only certificate observation (§11). Wraps the shared ``CertProbe``."""

from __future__ import annotations

from collections.abc import Sequence

from devteam_protocol import AgentRole

from devteam_organization.connectors.framework import ConnectorResult, ConnectorType
from devteam_organization.connectors.probes import CertProbe


class TLSConnector:
    id = "tls"
    name = "TLS Certificate"
    type = ConnectorType.TLS
    owner = AgentRole.CISO

    def __init__(self, hosts: Sequence[str], probe: CertProbe) -> None:
        self._hosts = tuple(hosts)
        self._probe = probe

    @property
    def enabled(self) -> bool:
        return bool(self._hosts)

    def fetch(self) -> ConnectorResult:
        if not self._hosts:
            return ConnectorResult.unavailable("no TLS hosts configured")
        rows: list[dict[str, object]] = []
        for host in self._hosts:
            result = self._probe(host)
            rows.append(
                {
                    "host": host,
                    "ok": result.ok,
                    "days_to_expiry": result.days_to_expiry,
                    "hostname_valid": result.hostname_valid,
                    "issuer": result.issuer,
                    "error": result.error,
                }
            )
        return ConnectorResult.okay({"hosts": rows})
