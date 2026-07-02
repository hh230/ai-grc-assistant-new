"""Read framework definition / mapping data from files and assemble a catalog.

A thin infrastructure adapter over the pure loader: it parses a structured data file (JSON
today; YAML plugs in behind ``_read_mapping`` with a parser dependency — a dependency choice,
not an architectural one) and hands the parsed mapping to ``load_framework`` / ``load_mapping_set``.
Framework definitions live under ``/frameworks/<id>/<version>/`` per ADR-0007.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from grc_domain.frameworks import Framework, FrameworkMappingSet

from .catalog import FrameworkCatalog
from .exceptions import FrameworkValidationError
from .loader import load_framework, load_mapping_set


def load_framework_file(path: Path) -> Framework:
    return load_framework(_read_mapping(path))


def load_mapping_file(path: Path) -> FrameworkMappingSet:
    return load_mapping_set(_read_mapping(path))


def build_catalog(
    *,
    framework_files: Iterable[Path] = (),
    mapping_files: Iterable[Path] = (),
) -> FrameworkCatalog:
    """Build a catalog by loading the given framework and mapping-set files."""
    catalog = FrameworkCatalog()
    for path in framework_files:
        catalog.register_framework(load_framework_file(path))
    for path in mapping_files:
        catalog.register_mapping_set(load_mapping_file(path))
    return catalog


def _read_mapping(path: Path) -> Mapping[str, object]:
    suffix = path.suffix.lower()
    if suffix != ".json":
        raise FrameworkValidationError(
            f"Unsupported framework data format {suffix!r} for {path}; expected '.json'"
        )
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        raise FrameworkValidationError(f"{path} must contain an object at the top level")
    return parsed
