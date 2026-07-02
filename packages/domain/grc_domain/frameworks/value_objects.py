"""Value objects for the Frameworks bounded context.

A framework definition is essentially immutable reference *data* (CLAUDE.md §13:
"frameworks are data, not code"). We model its structure with value objects nested inside
the Framework aggregate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.identifiers import FrameworkControlId, FrameworkId
from .enums import MappingRelation


@dataclass(frozen=True)
class FrameworkVersion:
    """A framework version label, e.g. '2.0'. Assessments pin the version they ran against."""

    label: str

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("FrameworkVersion label must not be empty")

    def __str__(self) -> str:
        return self.label


@dataclass(frozen=True)
class Requirement:
    """An atomic requirement under a framework control."""

    code: str
    text: str


@dataclass(frozen=True)
class EvidenceExpectation:
    """What kind of evidence demonstrates a control is operating."""

    description: str


@dataclass(frozen=True)
class FrameworkControl:
    """A control/requirement node within a framework definition (immutable data)."""

    id: FrameworkControlId
    code: str  # human reference, e.g. "1-2-3"
    title: str
    domain: str  # the framework domain/family this control belongs to
    requirements: tuple[Requirement, ...] = field(default_factory=tuple)
    evidence_expectations: tuple[EvidenceExpectation, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FrameworkControlRef:
    """A stable cross-context reference to a control inside a specific framework."""

    framework_id: FrameworkId
    framework_control_id: FrameworkControlId


@dataclass(frozen=True)
class ControlCorrespondence:
    """A single mapping between a source and target framework control."""

    source: FrameworkControlRef
    target: FrameworkControlRef
    relation: MappingRelation
