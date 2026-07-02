"""Framework Engine: compliance frameworks as data, plus cross-mapping.

Frameworks are **data, not code** (CLAUDE.md §13, ADR-0007). This package loads and validates
framework definitions and cross-framework mappings against a canonical schema, translates them
into the ``frameworks`` domain aggregates (an anti-corruption layer over untrusted data), and
serves them through an in-memory catalog (lookup, cross-framework mapping, coverage). It depends
only on ``grc_domain`` and never hardcodes a framework name into control flow.
"""
from __future__ import annotations

from .catalog import CoverageReport, FrameworkCatalog
from .exceptions import (
    FrameworkEngineError,
    FrameworkValidationError,
    UnknownFrameworkError,
    UnknownMappingSetError,
)
from .files import build_catalog, load_framework_file, load_mapping_file
from .loader import load_framework, load_mapping_set

__all__ = [
    # loading
    "load_framework",
    "load_mapping_set",
    "load_framework_file",
    "load_mapping_file",
    "build_catalog",
    # catalog
    "FrameworkCatalog",
    "CoverageReport",
    # exceptions
    "FrameworkEngineError",
    "FrameworkValidationError",
    "UnknownFrameworkError",
    "UnknownMappingSetError",
]
