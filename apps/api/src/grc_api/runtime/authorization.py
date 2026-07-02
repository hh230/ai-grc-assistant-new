"""RBAC authorization adapter for the application's ``AuthorizationService`` port.

Enforcement is **default deny** (CLAUDE.md §6 #10, ADR-0014): an action is permitted only when
at least one of the principal's roles explicitly grants the ``(Action, ResourceType)`` pair.
Coarse roles live in the domain (``UserRole``); the fine-grained matrix is an application-layer
policy and lives here. Tenant isolation is orthogonal and enforced separately by the
repositories — this service decides *what* a principal may do, never *whose* data they reach.

This is a deliberately simple, declarative policy engine. A production deployment may replace it
with an external ABAC/policy service behind the same port without touching any use case.
"""

from __future__ import annotations

from grc_domain.tenancy.enums import UserRole
from grc_services.shared.authorization import Action, AuthorizationService, ResourceType
from grc_services.shared.context import ExecutionContext
from grc_services.shared.exceptions import AuthorizationError

_ALL_ACTIONS: frozenset[Action] = frozenset(Action)
_READ: frozenset[Action] = frozenset({Action.READ})
_AUTHOR: frozenset[Action] = frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.EXECUTE})

_OPERATIONAL: frozenset[ResourceType] = frozenset(
    {
        ResourceType.MISSION,
        ResourceType.WORKSPACE,
        ResourceType.CONTROL,
        ResourceType.POLICY,
        ResourceType.RISK,
        ResourceType.ASSESSMENT,
        ResourceType.EVIDENCE,
        ResourceType.REPORT,
        ResourceType.KNOWLEDGE_SOURCE,
    }
)
_CATALOG: frozenset[ResourceType] = frozenset(
    {ResourceType.FRAMEWORK, ResourceType.TOOL, ResourceType.AGENT, ResourceType.PLUGIN}
)

# role -> resource type -> allowed actions. Absent entries are denied.
Matrix = dict[ResourceType, frozenset[Action]]


def _grant(resources: frozenset[ResourceType], actions: frozenset[Action]) -> Matrix:
    return dict.fromkeys(resources, actions)


def _merge(*matrices: Matrix) -> Matrix:
    merged: Matrix = {}
    for matrix in matrices:
        for resource, actions in matrix.items():
            merged[resource] = merged.get(resource, frozenset()) | actions
    return merged


_ALL_RESOURCES: frozenset[ResourceType] = frozenset(ResourceType)

_POLICY: dict[UserRole, Matrix] = {
    # Platform administrators: everything, everywhere.
    UserRole.OWNER: _grant(_ALL_RESOURCES, _ALL_ACTIONS),
    UserRole.ADMIN: _grant(_ALL_RESOURCES, _ALL_ACTIONS),
    # Compliance managers run the full operational lifecycle (incl. approve/publish), read
    # the catalog, and read the audit trail.
    UserRole.COMPLIANCE_MANAGER: _merge(
        _grant(_OPERATIONAL, _ALL_ACTIONS),
        _grant(_CATALOG, _READ),
        _grant(frozenset({ResourceType.AUDIT}), _READ),
    ),
    # Risk managers own risks end to end and can drive missions; read elsewhere.
    UserRole.RISK_MANAGER: _merge(
        _grant(frozenset({ResourceType.RISK}), _ALL_ACTIONS),
        _grant(frozenset({ResourceType.MISSION}), _AUTHOR),
        _grant(_OPERATIONAL - {ResourceType.RISK, ResourceType.MISSION}, _READ),
        _grant(_CATALOG, _READ),
        _grant(frozenset({ResourceType.AUDIT}), _READ),
    ),
    # Analysts author and execute operational work but cannot approve/publish/delete.
    UserRole.ANALYST: _merge(
        _grant(_OPERATIONAL, _AUTHOR),
        _grant(_CATALOG, _READ),
    ),
    # Auditors read everything, including the audit trail; never write.
    UserRole.AUDITOR: _grant(_ALL_RESOURCES, _READ),
    # Viewers read operational + catalog data, but not the audit trail.
    UserRole.VIEWER: _merge(
        _grant(_OPERATIONAL, _READ),
        _grant(_CATALOG, _READ),
    ),
}


class RbacAuthorizationService(AuthorizationService):
    """Default-deny role-based authorization over the application action/resource vocabulary."""

    async def can(
        self,
        context: ExecutionContext,
        action: Action,
        resource_type: ResourceType,
        resource_id: str | None = None,
    ) -> bool:
        for role in context.principal.roles:
            matrix = _POLICY.get(role)
            if matrix and action in matrix.get(resource_type, frozenset()):
                return True
        return False

    async def ensure_can(
        self,
        context: ExecutionContext,
        action: Action,
        resource_type: ResourceType,
        resource_id: str | None = None,
    ) -> None:
        if not await self.can(context, action, resource_type, resource_id):
            raise AuthorizationError(
                f"principal is not permitted to {action.value} {resource_type.value}"
            )
