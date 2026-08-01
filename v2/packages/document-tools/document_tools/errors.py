"""Document tool errors (CLAUDE.md §22: explicit, fail-safe). These surface as a failed
`ToolStepResult` (ok=False) rather than a raised exception across the tool boundary, so the Mission
Engine fails the mission safe (ADR 0042 §7) instead of crashing the executor."""

from __future__ import annotations


class DocumentToolError(Exception):
    """Base class for document-tool errors."""


class DocumentAccessError(DocumentToolError):
    """The requested path is missing, empty, or escapes the configured document root."""
