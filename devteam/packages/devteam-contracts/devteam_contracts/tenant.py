"""The reserved internal tenant the platform maintains itself under (ADR 0061 rule 1).

The dev team runs as a single, reserved tenant — ``tenant:platform`` — so every tenant-scoped
guarantee of the frozen v2 Core (mission isolation, tenant-stamped events and audit, cross-tenant
read refusal — ADR 0040) applies to dev work unchanged, and dev activity can never mix with a
customer tenant's data. This module only *constructs* the platform ``TenantContext``; it adds no
tenancy mechanism (that is ``pipeline_contracts.TenantContext``).
"""

from __future__ import annotations

from pipeline_contracts import TenantContext

# The reserved organization id for the platform's own engineering work. A specific, non-wildcard id
# (ADR 0040 forbids wildcard/absent tenants), never reused by a customer organization.
PLATFORM_TENANT_ID = "platform"

# The default principal the Foreman acts as when it opens dev missions. A service principal, not a
# human; RBAC over what it may do lives above the aggregate (ADR 0044/0054), never here.
FOREMAN_PRINCIPAL = "devteam-foreman"


def platform_tenant(
    principal_id: str = FOREMAN_PRINCIPAL,
    *,
    roles: tuple[str, ...] = (),
) -> TenantContext:
    """Build the platform ``TenantContext`` a dev mission runs under. ``principal_id`` names the
    dev-team actor (the Foreman by default, or a specific agent); ``roles`` back the future
    authorization phase (ADR 0054) and default empty."""
    return TenantContext(tenant_id=PLATFORM_TENANT_ID, principal_id=principal_id, roles=roles)
