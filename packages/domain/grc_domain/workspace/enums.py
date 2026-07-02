"""Enumerations for the Workspace bounded context."""
from __future__ import annotations

from enum import Enum


class WorkspaceStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
