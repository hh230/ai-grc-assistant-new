"""grc_services — the Application Layer of the AI GRC Assistant (Clean Architecture).

This package orchestrates use cases over the pure Domain Layer (`grc_domain`). It depends
**only** on the domain — never on FastAPI, SQLAlchemy, databases, AI/LLM SDKs, or any
other infrastructure (those depend inward on this layer).

It provides:

- CQRS messages: ``Command`` / ``Query`` and their handlers.
- DTOs: plain, boundary-friendly read models.
- Use cases: realized as command/query handlers, grouped behind per-capability
  ``ApplicationService`` facades.
- Ports & abstractions (in ``shared``): ``UnitOfWork`` (transaction boundary),
  ``AuthorizationService``, ``EventDispatcher``, ``Validator``, ``Clock`` / ``IdGenerator``,
  ``CommandBus`` / ``QueryBus``, ``Result`` types, and the application exception hierarchy.

Capabilities (subpackages): ``missions``, ``workspaces``, ``policies``, ``risks``,
``assessments``, ``evidence``, ``frameworks``, ``knowledge``, ``controls``, ``reporting``,
``tools``, ``agents``, ``plugins``, ``audit``.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

# Lazy (PEP 562) exports. The application-service facades are imported on first access
# rather than eagerly at package import. This is import hygiene only — it changes no use
# case or business rule — but it keeps a single context that is structurally blocked (the
# Knowledge capability, deferred pending the M5↔M3 re-alignment, ADL-0008) from breaking
# the import of every healthy sibling. Accessing the blocked facade still raises, by design.
_EXPORTS: dict[str, str] = {
    "MissionApplicationService": ".missions",
    "WorkspaceApplicationService": ".workspaces",
    "PolicyApplicationService": ".policies",
    "RiskApplicationService": ".risks",
    "AssessmentApplicationService": ".assessments",
    "EvidenceApplicationService": ".evidence",
    "FrameworkApplicationService": ".frameworks",
    "KnowledgeApplicationService": ".knowledge",  # blocked — ADL-0008
    "ControlApplicationService": ".controls",
    "ReportingApplicationService": ".reporting",
    "ToolApplicationService": ".tools",
    "AgentApplicationService": ".agents",
    "PluginApplicationService": ".plugins",
    "AuditApplicationService": ".audit",
}

if TYPE_CHECKING:
    from .agents import AgentApplicationService
    from .assessments import AssessmentApplicationService
    from .audit import AuditApplicationService
    from .controls import ControlApplicationService
    from .evidence import EvidenceApplicationService
    from .frameworks import FrameworkApplicationService
    from .knowledge import KnowledgeApplicationService
    from .missions import MissionApplicationService
    from .plugins import PluginApplicationService
    from .policies import PolicyApplicationService
    from .reporting import ReportingApplicationService
    from .risks import RiskApplicationService
    from .tools import ToolApplicationService
    from .workspaces import WorkspaceApplicationService


def __getattr__(name: str) -> object:
    module_path = _EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_path, __name__)
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(_EXPORTS)


__all__ = [
    "MissionApplicationService",
    "WorkspaceApplicationService",
    "PolicyApplicationService",
    "RiskApplicationService",
    "AssessmentApplicationService",
    "EvidenceApplicationService",
    "FrameworkApplicationService",
    "KnowledgeApplicationService",
    "ControlApplicationService",
    "ReportingApplicationService",
    "ToolApplicationService",
    "AgentApplicationService",
    "PluginApplicationService",
    "AuditApplicationService",
]

__version__ = "0.0.0"
