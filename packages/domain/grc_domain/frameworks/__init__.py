"""Frameworks bounded context: Framework definitions and cross-framework mappings."""
from __future__ import annotations

from .entities import Framework, FrameworkMappingSet
from .enums import FrameworkStatus, MappingRelation
from .repositories import FrameworkMappingRepository, FrameworkRepository
from .services import CrossFrameworkMappingService
from .value_objects import (
    ControlCorrespondence,
    EvidenceExpectation,
    FrameworkControl,
    FrameworkControlRef,
    FrameworkVersion,
    Requirement,
)

__all__ = [
    "Framework",
    "FrameworkMappingSet",
    "FrameworkStatus",
    "MappingRelation",
    "FrameworkRepository",
    "FrameworkMappingRepository",
    "CrossFrameworkMappingService",
    "ControlCorrespondence",
    "EvidenceExpectation",
    "FrameworkControl",
    "FrameworkControlRef",
    "FrameworkVersion",
    "Requirement",
]
