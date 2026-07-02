"""Enumerations for the Policies bounded context."""
from __future__ import annotations

from enum import Enum


class PolicyStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    RETIRED = "retired"
