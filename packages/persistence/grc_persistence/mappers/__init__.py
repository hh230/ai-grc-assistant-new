"""Mappers — the single home of Domain ↔ ORM (and Domain → integration event) translation.

Every module exposes ready-to-use singleton mapper instances that the repositories import.
No other package is permitted to translate between domain objects and ORM rows.
"""

from __future__ import annotations

from .assessments import assessment_mapper
from .audit import audit_record_mapper
from .controls import control_mapper
from .events import (
    integration_event_to_model,
    serialize_event_payload,
    to_integration_event,
)
from .evidence import evidence_mapper
from .frameworks import framework_mapper, framework_mapping_set_mapper
from .knowledge import knowledge_source_mapper
from .missions import (
    mission_gate_child_mapper,
    mission_mapper,
    mission_step_child_mapper,
)
from .platform import (
    agent_descriptor_mapper,
    plugin_descriptor_mapper,
    tool_descriptor_mapper,
)
from .policies import policy_mapper
from .reporting import report_mapper
from .risks import risk_mapper
from .tenancy import organization_mapper, user_mapper
from .workspace import workspace_mapper

__all__ = [
    "organization_mapper",
    "user_mapper",
    "workspace_mapper",
    "framework_mapper",
    "framework_mapping_set_mapper",
    "control_mapper",
    "policy_mapper",
    "risk_mapper",
    "assessment_mapper",
    "evidence_mapper",
    "knowledge_source_mapper",
    "report_mapper",
    "tool_descriptor_mapper",
    "agent_descriptor_mapper",
    "plugin_descriptor_mapper",
    "mission_mapper",
    "mission_step_child_mapper",
    "mission_gate_child_mapper",
    "audit_record_mapper",
    "to_integration_event",
    "integration_event_to_model",
    "serialize_event_payload",
]
