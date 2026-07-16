"""Tool Registry errors — raised loudly so misuse fails at the boundary (CLAUDE.md §22)."""

from __future__ import annotations


class ToolRegistryError(Exception):
    """Base of every registry error."""


class InvalidToolSpec(ToolRegistryError, ValueError):
    """A tool declared an invalid spec — e.g. an empty name or a version below 1. A subclass
    of ValueError so an invalid spec fails at construction, never silently."""


class ToolNotFound(ToolRegistryError):
    """No tool with that name (or that version of it) is registered, or the caller may not see
    it. Note the scoping: a tool the caller lacks the role to access is *not found* to them."""


class ToolAlreadyRegistered(ToolRegistryError):
    """A tool with the same name and version is already registered. Breaking changes ship as a
    new version (CLAUDE.md §10); re-registering an existing version is a mistake, not an update."""
