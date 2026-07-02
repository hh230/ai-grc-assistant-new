"""Authentication — turning a bearer credential into a tenant-bound ``Principal``.

Authentication is abstracted behind the ``TokenAuthenticator`` port so the verification
mechanism is swappable without touching routes (ADR-0014: OIDC/SSO in production). The shipped
adapter is a **static bearer-token** authenticator for local/dev/test and CI; a production
deployment binds an OIDC/JWT authenticator behind the same port. Either way the result is a
``Principal`` carrying the tenant (``organization_id``), the user, and the RBAC roles — the
identity every use case is scoped and authorized against. Default deny: an unknown or malformed
token yields no principal.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from grc_domain.shared.identifiers import OrganizationId, UserId
from grc_domain.tenancy.enums import UserRole
from grc_services.shared.context import Principal

from ..middleware.errors import InvalidTokenError


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    """Build a Principal from a claims mapping. Raises ValueError on malformed claims."""
    try:
        user_id = str(claims["user_id"])
        organization_id = str(claims["organization_id"])
    except KeyError as exc:
        raise ValueError(f"principal claims missing required field: {exc}") from exc
    raw_roles = claims.get("roles", [])
    if not isinstance(raw_roles, (list, tuple)):
        raise ValueError("principal 'roles' must be a list")
    roles: set[UserRole] = set()
    for raw in raw_roles:
        try:
            roles.add(UserRole(str(raw)))
        except ValueError as exc:
            raise ValueError(f"unknown role {raw!r}") from exc
    return Principal(
        user_id=UserId(user_id),
        organization_id=OrganizationId(organization_id),
        roles=frozenset(roles),
    )


class TokenAuthenticator(ABC):
    """Outbound port: verify a bearer token and return the authenticated principal."""

    @abstractmethod
    async def authenticate(self, token: str) -> Principal: ...


class StaticTokenAuthenticator(TokenAuthenticator):
    """Verifies tokens against a fixed in-memory map (dev/test/CI). Default deny on miss."""

    def __init__(self, tokens: dict[str, Principal]) -> None:
        self._tokens = dict(tokens)

    async def authenticate(self, token: str) -> Principal:
        principal = self._tokens.get(token)
        if principal is None:
            raise InvalidTokenError("the provided bearer token is not recognized")
        return principal

    @property
    def token_count(self) -> int:
        return len(self._tokens)
