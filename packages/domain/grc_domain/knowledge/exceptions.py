"""Exceptions for the Knowledge bounded context.

Each subclasses a shared-kernel domain error so callers can catch by category.
"""
from __future__ import annotations

from ..shared.exceptions import (
    ApprovalRequired,
    InvalidStateTransition,
    InvariantViolation,
    NotFoundError,
)


class IllegalVersionTransition(InvalidStateTransition):
    """Raised when a source version is moved through an illegal lifecycle transition."""


class IllegalKnowledgeObjectTransition(InvalidStateTransition):
    """Raised when a knowledge object is moved through an illegal curation transition."""


class IllegalRelationshipTransition(InvalidStateTransition):
    """Raised when a relationship is moved through an illegal curation transition."""


class PublishRequiresApproval(ApprovalRequired):
    """Raised when publishing a version is attempted without a recorded approval (human gate)."""


class VersionRequiresDocument(InvariantViolation):
    """Raised when publishing a version that has no documents."""


class VersionImmutable(InvariantViolation):
    """Raised when mutating the content of a version that is no longer editable."""


class SelfReferentialRelationship(InvariantViolation):
    """Raised when a relationship would connect an endpoint to itself."""


class KnowledgeDocumentNotFound(NotFoundError):
    """Raised when a document is not found within a version."""


class KnowledgeSectionNotFound(NotFoundError):
    """Raised when a section is not found within a document."""
