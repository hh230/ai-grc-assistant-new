"""Read regulatory source definitions from local JSON config files (mirrors
``grc_framework_engine.files``'s role for frameworks — CLAUDE.md §13: configuration, not
code). Sources live under ``/regulatory-sources/<jurisdiction>/<source_id>.json``.

Only the standard library (``json``, ``pathlib``) is used — this stays consistent with the
package's "no external dependencies" rule; it is local, static config data, not network I/O.

Canonical source schema (a parsed mapping)::

    {
      "source_id": "sa-sama",
      "regulator_name": "Saudi Central Bank (SAMA)",
      "jurisdiction": "SA",
      "language": "ar",
      "base_url": "https://www.sama.gov.sa",
      "source_type": "website",
      "polling_frequency": "weekly",
      "enabled": true
    }
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from .sources import PollingFrequency, RegulatorySource, RegulatorySourceRegistry, SourceType


def load_source(data: Mapping[str, object]) -> RegulatorySource:
    """Validate and translate a source definition mapping into a ``RegulatorySource``."""
    return RegulatorySource(
        source_id=_require_str(data, "source_id"),
        regulator_name=_require_str(data, "regulator_name"),
        jurisdiction=_require_str(data, "jurisdiction"),
        language=_require_str(data, "language"),
        base_url=_require_str(data, "base_url"),
        source_type=_load_source_type(_require_str(data, "source_type")),
        polling_frequency=_load_polling_frequency(_require_str(data, "polling_frequency")),
        enabled=bool(data.get("enabled", True)),
    )


def load_source_file(path: Path) -> RegulatorySource:
    if path.suffix.lower() != ".json":
        raise ValueError(
            f"Unsupported source config format {path.suffix!r} for {path}; expected '.json'"
        )
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError(f"{path} must contain an object at the top level")
    return load_source(parsed)


def build_registry(source_files: Iterable[Path] = ()) -> RegulatorySourceRegistry:
    """Build a registry by loading every given source config file."""
    registry = RegulatorySourceRegistry()
    for path in source_files:
        registry.register(load_source_file(path))
    return registry


def _require_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key!r} must be a non-empty string")
    return value


def _load_source_type(raw: str) -> SourceType:
    try:
        return SourceType(raw)
    except ValueError as exc:
        valid = ", ".join(member.value for member in SourceType)
        raise ValueError(f"source_type {raw!r} is not one of: {valid}") from exc


def _load_polling_frequency(raw: str) -> PollingFrequency:
    try:
        return PollingFrequency(raw)
    except ValueError as exc:
        valid = ", ".join(member.value for member in PollingFrequency)
        raise ValueError(f"polling_frequency {raw!r} is not one of: {valid}") from exc
