"""Shared enumerations used across multiple bounded contexts."""
from __future__ import annotations

from enum import Enum


class ConfidenceLevel(str, Enum):
    """Coarse confidence band derived from a numeric confidence score."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DataClassification(str, Enum):
    """Sensitivity classification for data the platform handles."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
