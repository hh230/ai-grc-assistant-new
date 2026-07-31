"""Website + HTTP-security connectors — read-only HTTP observation (§11).

Both wrap the shared ``HttpProbe`` (no duplicated integration). The website connector reports
availability, status code, and response time per endpoint; the security connector reports which
required security headers are missing. No endpoints configured ⇒ Unavailable (the job stays idle).
"""

from __future__ import annotations

from collections.abc import Sequence

from devteam_protocol import AgentRole

from devteam_organization.connectors.config import Endpoint
from devteam_organization.connectors.framework import ConnectorResult, ConnectorType
from devteam_organization.connectors.probes import HttpProbe

# The security headers a hardened HTTP response is expected to carry (spec adds Permissions-Policy).
_REQUIRED_HEADERS = {
    "strict-transport-security": "HSTS",
    "content-security-policy": "CSP",
    "x-frame-options": "X-Frame-Options",
    "x-content-type-options": "X-Content-Type-Options",
    "referrer-policy": "Referrer-Policy",
    "permissions-policy": "Permissions-Policy",
}


class WebsiteConnector:
    id = "website"
    name = "Website"
    type = ConnectorType.WEBSITE
    owner = AgentRole.CISO

    def __init__(
        self, endpoints: Sequence[Endpoint], probe: HttpProbe, *, slow_ms: float = 3000.0
    ) -> None:
        self._endpoints = tuple(endpoints)
        self._probe = probe
        self._slow_ms = slow_ms

    @property
    def enabled(self) -> bool:
        return bool(self._endpoints)

    def fetch(self) -> ConnectorResult:
        if not self._endpoints:
            return ConnectorResult.unavailable("no endpoints configured")
        rows: list[dict[str, object]] = []
        for endpoint in self._endpoints:
            result = self._probe(endpoint.url)
            rows.append(
                {
                    "name": endpoint.name,
                    "url": endpoint.url,
                    "ok": result.ok,
                    "status": result.status,
                    "elapsed_ms": result.elapsed_ms,
                    "slow": bool(result.elapsed_ms and result.elapsed_ms > self._slow_ms),
                    "error": result.error,
                }
            )
        return ConnectorResult.okay({"endpoints": rows})


class HttpSecurityConnector:
    id = "http_security"
    name = "HTTP Security Headers"
    type = ConnectorType.HTTP_SECURITY
    owner = AgentRole.CISO

    def __init__(self, endpoints: Sequence[Endpoint], probe: HttpProbe) -> None:
        self._endpoints = tuple(endpoints)
        self._probe = probe

    @property
    def enabled(self) -> bool:
        return bool(self._endpoints)

    def fetch(self) -> ConnectorResult:
        if not self._endpoints:
            return ConnectorResult.unavailable("no endpoints configured")
        rows: list[dict[str, object]] = []
        for endpoint in self._endpoints:
            result = self._probe(endpoint.url)
            reachable = result.status is not None
            missing = [
                label
                for header, label in _REQUIRED_HEADERS.items()
                if reachable and header not in result.headers
            ]
            rows.append(
                {
                    "name": endpoint.name,
                    "url": endpoint.url,
                    "reachable": reachable,
                    "missing": missing,
                    "present": [
                        label for header, label in _REQUIRED_HEADERS.items()
                        if header in result.headers
                    ],
                }
            )
        return ConnectorResult.okay({"endpoints": rows})
