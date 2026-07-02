"""Authorization interfaces (ports).

The application declares *what* must be authorized; the concrete policy engine lives in
infrastructure. Handlers call `ensure_can(...)`, which raises `AuthorizationError` when the
principal is not permitted.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from .context import ExecutionContext


class Action(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    EXECUTE = "execute"
    PUBLISH = "publish"


class ResourceType(str, Enum):
    MISSION = "mission"
    WORKSPACE = "workspace"
    POLICY = "policy"
    RISK = "risk"
    ASSESSMENT = "assessment"
    EVIDENCE = "evidence"
    CONTROL = "control"
    FRAMEWORK = "framework"
    KNOWLEDGE_SOURCE = "knowledge_source"
    REPORT = "report"
    TOOL = "tool"
    AGENT = "agent"
    PLUGIN = "plugin"
    AUDIT = "audit"


class AuthorizationService(ABC):
    """Outbound port: decides whether a principal may perform an action."""

    @abstractmethod
    async def can(
        self,
        context: ExecutionContext,
        action: Action,
        resource_type: ResourceType,
        resource_id: str | None = None,
    ) -> bool: ...

    @abstractmethod
    async def ensure_can(
        self,
        context: ExecutionContext,
        action: Action,
        resource_type: ResourceType,
        resource_id: str | None = None,
    ) -> None:
        """Raise AuthorizationError if the action is not permitted."""
        ...
