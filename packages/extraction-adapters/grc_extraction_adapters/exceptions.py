"""Errors raised by the concrete extraction adapters.

These surface at the engine's per-stage boundary, where the pipeline wraps them into a fail-safe
``ExtractionError`` and fails the run without partial publication.
"""
from __future__ import annotations


class AdapterError(Exception):
    """Base class for extraction-adapter errors."""


class DocumentNotAvailableError(AdapterError):
    """Raised when a document adapter cannot obtain the bytes for a storage locator."""
