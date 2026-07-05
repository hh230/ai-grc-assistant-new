"""The caller-facing context every Tool invocation carries.

CLAUDE.md §9 names six callers a Tool must be invocable from with identical semantics:
the Orchestrator, the API, the UI, the Workflow Engine, Scheduled Jobs, and Tests.
``ToolCaller`` names them so the audit trail (CLAUDE.md §19) always records *who* ran a tool,
not just *that* it ran. ``ToolContext`` is the tenant/auth context (CLAUDE.md §9): every
invocation is tenant-scoped and identity-bound, with one narrow exception — platform-scope
tools (e.g. polling a regulatory source, which is shared reference data, not tenant data)
pass ``tenant_id=None`` explicitly rather than omitting tenancy by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ToolCaller(str, Enum):
    """The six callers every Tool must be invocable from (CLAUDE.md §9)."""

    ORCHESTRATOR = "orchestrator"
    API = "api"
    UI = "ui"
    WORKFLOW = "workflow"
    SCHEDULED_JOB = "scheduled_job"
    TEST = "test"


@dataclass(frozen=True)
class ToolContext:
    """Who is invoking a tool, on whose behalf, and how.

    ``tenant_id`` is ``None`` only for platform-scope operations against shared reference
    data (frameworks, regulatory obligations) — never for anything touching customer data.
    """

    caller: ToolCaller
    tenant_id: str | None
    user_id: str
    roles: frozenset[str] = field(default_factory=frozenset)
    agent: str | None = None
    idempotency_key: str | None = None

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("ToolContext.user_id must not be empty")
