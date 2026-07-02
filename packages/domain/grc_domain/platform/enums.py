"""Enumerations for the Platform bounded context (Tool / Agent / Plugin descriptors)."""
from __future__ import annotations

from enum import Enum


class ToolSideEffect(str, Enum):
    """Whether invoking a tool changes state (drives human-gate requirements)."""

    READ_ONLY = "read_only"
    CONSEQUENTIAL = "consequential"


class ToolStatus(str, Enum):
    REGISTERED = "registered"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class AgentType(str, Enum):
    KNOWLEDGE = "knowledge"
    POLICY = "policy"
    COMPLIANCE = "compliance"
    RISK = "risk"
    REPORT = "report"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    REGISTERED = "registered"
    DISABLED = "disabled"


class PluginStatus(str, Enum):
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
