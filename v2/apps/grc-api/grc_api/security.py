"""Auth + Tenant Context — the single seam the whole API resolves its tenant through (ADR 0052).

The API depends on an **`IdentityProvider`**: it maps an opaque credential to a `TenantContext`. V1
ships a `DevelopmentIdentityProvider` (a seeded credential → tenant map); deployment swaps in an
OIDC provider with **zero route change** — every route depends on `require_tenant`, which returns a
`TenantContext` either way. The credential *transport* (a bearer header) lives in `require_tenant`,
so "bearer" is a transport detail, never part of the design. RBAC enforcement is deferred (the
contract's role guards stay declared); here `roles` travel on the context as data.

Fail-closed: a request with no credential, or an unrecognised one, is `401` — never an anonymous or
widened tenant.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from fastapi import Request
from pipeline_contracts import TenantContext

from grc_api.errors import ApiError


@runtime_checkable
class IdentityProvider(Protocol):
    """Resolve a credential to the caller's tenant, or `None` if unrecognised. The one auth seam:
    `DevelopmentIdentityProvider` in dev, an OIDC provider in deployment — same return type."""

    def resolve(self, credential: str) -> TenantContext | None: ...


class DevelopmentIdentityProvider:
    """Dev-only provider: a fixed credential → tenant map. The seam OIDC replaces in deployment."""

    def __init__(self, credentials: dict[str, TenantContext]) -> None:
        self._credentials = dict(credentials)

    def resolve(self, credential: str) -> TenantContext | None:
        return self._credentials.get(credential)


def development_identity_provider() -> DevelopmentIdentityProvider:
    """Seeded dev tenants — enough to exercise tenant isolation and the Approver gate locally/in
    tests. `dev-approver-a` is a tenant-a principal who also holds the Approver role."""
    return DevelopmentIdentityProvider(
        {
            "dev-tenant-a": TenantContext(
                tenant_id="tenant-a",
                principal_id="practitioner@a",
                roles=("practitioner",),
                region="ksa",
            ),
            "dev-approver-a": TenantContext(
                tenant_id="tenant-a",
                principal_id="approver@a",
                roles=("practitioner", "approver"),
                region="ksa",
            ),
            "dev-tenant-b": TenantContext(
                tenant_id="tenant-b",
                principal_id="practitioner@b",
                roles=("practitioner",),
                region="ksa",
            ),
        }
    )


def require_tenant(request: Request) -> TenantContext:
    """FastAPI dependency: resolve the caller's tenant, fail-closed. The bearer header is the
    transport for the credential; the `IdentityProvider` maps it to a tenant."""
    header = request.headers.get("Authorization", "")
    scheme, _, credential = header.partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        raise ApiError(status_code=401, code="unauthorized", message="missing credential")
    identity: IdentityProvider = request.app.state.identity_provider
    tenant = identity.resolve(credential.strip())
    if tenant is None:
        raise ApiError(status_code=401, code="unauthorized", message="invalid credential")
    return tenant
