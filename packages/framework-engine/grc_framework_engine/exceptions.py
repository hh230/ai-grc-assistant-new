"""Errors raised by the Framework Engine when loading/validating/looking up framework data."""
from __future__ import annotations


class FrameworkEngineError(Exception):
    """Base class for Framework Engine errors."""


class FrameworkValidationError(FrameworkEngineError):
    """Raised when framework definition data does not conform to the canonical schema."""


class UnknownFrameworkError(FrameworkEngineError):
    """Raised when a requested framework (or version) is not registered in the catalog."""


class UnknownMappingSetError(FrameworkEngineError):
    """Raised when a requested cross-framework mapping set is not registered."""
