"""Enumerations for the Knowledge Extraction bounded context.

These describe the *process* of turning raw documents into canonical Knowledge Objects.
Parsing libraries, OCR, and any AI model are infrastructure behind ports and never appear
in the domain.
"""
from __future__ import annotations

from enum import Enum


class ExtractionRunStatus(str, Enum):
    """Lifecycle of a durable, resumable extraction run."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class ExtractionStage(str, Enum):
    """The ordered pipeline stages from raw document to persisted candidates."""

    INTAKE = "intake"
    PARSE = "parse"
    NORMALIZE = "normalize"
    SEGMENT = "segment"
    CLASSIFY = "classify"
    EXTRACT_OBJECTS = "extract_objects"
    EXTRACT_RELATIONSHIPS = "extract_relationships"
    SCORE = "score"
    PERSIST = "persist"


class StageStatus(str, Enum):
    """Outcome of a single stage execution (one attempt)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
