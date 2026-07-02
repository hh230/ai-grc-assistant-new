"""Enumerations for the Controls bounded context."""
from __future__ import annotations

from enum import Enum


class ControlImplementationStatus(str, Enum):
    NOT_IMPLEMENTED = "not_implemented"
    PARTIALLY_IMPLEMENTED = "partially_implemented"
    IMPLEMENTED = "implemented"
    NOT_APPLICABLE = "not_applicable"
