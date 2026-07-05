"""Execution-time errors for the Tool Registry. Distinct from grc_domain's invariant errors —
these are runtime/registry concerns (lookup, permission, validation), not domain rule breaks.
"""

from __future__ import annotations


class ToolError(Exception):
    """Base class for Tool Registry errors."""


class ToolNotFoundError(ToolError):
    """No tool is registered for the requested name/version."""


class ToolPermissionDeniedError(ToolError):
    """The calling context lacks a permission the tool's descriptor requires."""


class ToolInputValidationError(ToolError):
    """The raw input failed validation against the tool's input model."""
