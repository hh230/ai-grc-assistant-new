"""`CommandContext` — the ambient inputs every command and query shares (ADR 0054).

Instead of threading identity and cross-cutting fields through every signature (and re-editing many
of them when a new concern appears), a service takes one context:

    ApproveMissionStepCommand().execute(context, mission_id, step_id)

**Identity is explicit, not derived from the tenant.** A tenant is *not* a user: Alice
(Practitioner), Bob (Approver), and Charlie (Admin) can all live in tenant `acme` with different
roles. So the principal id and roles are first-class fields, never read off the tenant — the
contract stays correct the day per-user roles matter. `tenant_context()` bridges to the Core's
`TenantContext` for store / engine calls. Locale/timezone/tracing join here later, untouched.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from pipeline_contracts import TenantContext


def _now() -> float:
    return time.time()


@dataclass(frozen=True)
class CommandContext:
    tenant_id: str
    principal_id: str
    roles: tuple[str, ...] = ()
    correlation_id: str = ""  # audit: ties related actions together
    request_id: str = ""  # events: the originating request
    clock: Callable[[], float] = _now  # injectable for testable timestamps

    def has_role(self, role: str) -> bool:
        """Authorization helper: does the acting principal hold this role?"""
        return role in self.roles

    def tenant_context(self) -> TenantContext:
        """The Core's tenant scope for store/engine calls — carries the principal + roles too."""
        return TenantContext(
            tenant_id=self.tenant_id, principal_id=self.principal_id, roles=self.roles
        )
