"""Execution context carried into every use case.

The context binds tenancy and identity to a request so handlers can enforce tenant
isolation and authorization, and so the audit trail can attribute actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.shared.identifiers import OrganizationId, UserId
from grc_domain.shared.value_objects import TraceContext
from grc_domain.tenancy.enums import UserRole


@dataclass(frozen=True)
class Principal:
    """The authenticated actor on whose behalf a use case runs."""

    user_id: UserId
    organization_id: OrganizationId
    roles: frozenset[UserRole] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ExecutionContext:
    """Tenant + identity + trace context for a single use-case invocation."""

    principal: Principal
    trace: TraceContext | None = None

    @property
    def organization_id(self) -> OrganizationId:
        return self.principal.organization_id

    @property
    def user_id(self) -> UserId:
        return self.principal.user_id
