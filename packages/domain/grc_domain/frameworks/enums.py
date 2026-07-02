"""Enumerations for the Frameworks bounded context."""
from __future__ import annotations

from enum import Enum


class FrameworkStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class MappingRelation(str, Enum):
    """Relationship between two framework controls in a cross-framework mapping."""

    EQUIVALENT = "equivalent"
    BROADER = "broader"
    NARROWER = "narrower"
    RELATED = "related"
