"""Framework Library errors (CLAUDE.md §22: errors are explicit, fail loud in dev)."""

from __future__ import annotations


class FrameworkLibraryError(Exception):
    """Base class for every Framework Library error."""


class FrameworkNotFound(FrameworkLibraryError):
    """A framework id was requested that the library has not loaded."""

    def __init__(self, framework_id: str, available: tuple[str, ...]) -> None:
        self.framework_id = framework_id
        self.available = available
        super().__init__(
            f"framework {framework_id!r} not loaded; available: {', '.join(available) or '(none)'}"
        )


class InvalidFrameworkDefinition(FrameworkLibraryError):
    """A framework definition file is missing required fields or is malformed."""
