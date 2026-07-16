"""Tenancy contract — the immutable `TenantContext` value object (ADR 0040 §3).

`TenantContext` is the single carrier of tenant scope across the platform. It is minted at
the authenticated request boundary from the verified identity, and then *carried* downstream
— never re-derived, widened, or inferred (ADR 0040 §3). This module defines the value object
and its invariants only.

This addition is **additive and backward-compatible**: it introduces the type into its
ADR-mandated home (the shared contract library) without touching any existing model. Making
`TenantContext` a *required* field on `UserRequest` and threading it through every stage is
the tenancy *implementation* — a deliberate, breaking, later change (ADR 0040 §4, §7). Until
then, no existing contract or caller changes, and the V2 pipeline remains single-corpus.

Two knowledge scopes exist, and only these (ADR 0040 §2): `GLOBAL` (frameworks, laws,
standards — owned by no one) and `ORGANIZATION` (a tenant's own data). Every tenant-scoped
read spans `GLOBAL ∪ ORGANIZATION(tenant_id)` and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pipeline_contracts.serialization import dataclass_dict

# Reserved identifiers that can never name a real tenant. A tenant is an opaque, stable id
# (ADR 0040 §1); these strings are the wildcard/"everything" values a bug or an injection
# attempt would try to smuggle in, and construction rejects them.
_WILDCARD_TENANTS = frozenset({"*", "all", "any", "none", "null"})


class KnowledgeScope(str, Enum):
    """The two — and only two — data scopes (ADR 0040 §2). A read spans GLOBAL plus the one
    ORGANIZATION named by the tenant; cross-organization reads do not exist at any scope."""

    GLOBAL = "global"
    ORGANIZATION = "organization"


class TenancyError(ValueError):
    """A tenancy invariant was violated — a missing/wildcard tenant, or a cross-tenant access.
    A subclass of `ValueError` so an invalid tenant fails loudly at construction, never
    silently as a default (CLAUDE.md §22; ADR 0040 §3)."""


@dataclass(frozen=True)
class TenantContext:
    """The immutable tenant scope of one run (ADR 0040 §3).

    `tenant_id` is the organization (`== organization_id`): required, never empty, never a
    wildcard. `principal_id` is the authenticated actor within that tenant (a user, a service,
    or an agent acting on their behalf). `roles` back RBAC/ABAC decisions. `region` is the
    data-residency region the run is bound to (CLAUDE.md §20).

    There is no default tenant and no `tenant_id=None` path meaning "everything": absent or
    wildcard tenant is an error, not a default (ADR 0040 §3 invariants). The object is frozen,
    so a run's tenant cannot be replaced or widened after it is minted."""

    tenant_id: str
    principal_id: str = ""
    roles: tuple[str, ...] = ()
    region: str = ""

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.tenant_id.strip():
            raise TenancyError("tenant_id is required: a run must name the tenant it serves")
        if self.tenant_id.strip().lower() in _WILDCARD_TENANTS:
            raise TenancyError(
                f"tenant_id may not be a wildcard ({self.tenant_id!r}): "
                "a tenant is a specific organization, never 'everything'"
            )
        # Normalize roles to an immutable tuple regardless of how they were passed in.
        object.__setattr__(self, "roles", tuple(self.roles))

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def same_tenant(self, other: TenantContext) -> bool:
        """Whether two contexts name the same organization. The one comparison the platform
        makes when it must confirm a caller may touch tenant-owned state (ADR 0040 §5)."""
        return self.tenant_id == other.tenant_id

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class RetrievalScope:
    """The boundary a retrieval is bound to (ADR 0040 §2) — modeled as a *scope*, not a bare
    tenant filter, so future dimensions (region, project, classification, business unit, legal
    entity, …) become additional fields here with **no change to `Filter` or the provider
    interface**.

    Today it carries one dimension, the organization:

    - `kind = ORGANIZATION` with a `tenant_id` → the retrieval spans `GLOBAL ∪
      ORGANIZATION(tenant_id)` (the two-library rule). This is what every tenant request uses.
    - `kind = GLOBAL` with `tenant_id = None` → the retrieval spans `GLOBAL` only (system /
      ingestion / admin reads that belong to no tenant).

    Global scope is represented **explicitly** (`kind=GLOBAL`, `tenant_id=None`) — never by an
    empty string. Absence of an organization is a real, named state, not a blank."""

    kind: KnowledgeScope
    tenant_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind is KnowledgeScope.ORGANIZATION and not (self.tenant_id or "").strip():
            raise TenancyError(
                "an ORGANIZATION retrieval scope requires a tenant_id"
            )
        if self.kind is KnowledgeScope.GLOBAL and self.tenant_id is not None:
            raise TenancyError(
                "a GLOBAL retrieval scope must not carry a tenant_id (it belongs to no tenant)"
            )

    @classmethod
    def for_tenant(cls, tenant_id: str) -> RetrievalScope:
        """The scope of a tenant's request: `GLOBAL ∪ ORGANIZATION(tenant_id)`."""
        return cls(kind=KnowledgeScope.ORGANIZATION, tenant_id=tenant_id)

    @classmethod
    def from_context(cls, context: TenantContext) -> RetrievalScope:
        """Derive the retrieval scope from a run's `TenantContext` — the pipeline's path."""
        return cls.for_tenant(context.tenant_id)

    @classmethod
    def global_only(cls) -> RetrievalScope:
        """A tenant-less scope over shared knowledge only (frameworks, laws, standards)."""
        return cls(kind=KnowledgeScope.GLOBAL, tenant_id=None)

    @property
    def includes_organization(self) -> bool:
        return self.kind is KnowledgeScope.ORGANIZATION

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)
