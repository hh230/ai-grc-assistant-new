"""Read the curated ``/trusted-sources`` catalog from local JSON config files (mirrors
``grc_regulatory_intelligence.source_config``'s role for regulators, and
``grc_framework_engine.files``/``grc_knowledge_intelligence.question_catalog`` for their own
data — CLAUDE.md §13: configuration, not code). Sources live under
``/trusted-sources/<jurisdiction>/<source_id>.json``.

Only the standard library (``json``, ``pathlib``) plus ``grc_knowledge_intelligence`` and
``grc_knowledge_research`` (both dependency-free) are used — this is local, static config
data, not network I/O.

Canonical source schema (a parsed mapping)::

    {
      "source_id": "sa-nca",
      "name": "National Cybersecurity Authority (NCA)",
      "source_type": "government_regulator",
      "url": "https://nca.gov.sa",
      "jurisdiction": "SA",
      "domains": ["cybersecurity_governance", "regulatory_obligations"]
    }

``source_type`` must be one of ``TrustedSourceType``'s five members and ``domains`` a
non-empty list of ``KnowledgeDomain`` values — a malformed or uncataloged entry fails to load
rather than silently becoming a trusted source ("do not use random blogs" is enforced here by
construction, the same as it is in ``grc_knowledge_intelligence.models.TrustedSource``).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from grc_knowledge_intelligence import KnowledgeDomain, TrustedSource, TrustedSourceType
from grc_knowledge_research import CatalogedSource


def load_cataloged_source(data: Mapping[str, object]) -> CatalogedSource:
    """Validate and translate a trusted-source definition mapping into a ``CatalogedSource``."""
    source = TrustedSource(
        source_id=_require_str(data, "source_id"),
        name=_require_str(data, "name"),
        source_type=_load_source_type(_require_str(data, "source_type")),
        url=_require_str(data, "url"),
        jurisdiction=_require_str(data, "jurisdiction"),
    )
    domains = tuple(_load_domain(value) for value in _require_domains(data))
    return CatalogedSource(source=source, domains=domains)


def load_cataloged_source_file(path: Path) -> CatalogedSource:
    if path.suffix.lower() != ".json":
        raise ValueError(
            f"Unsupported trusted source config format {path.suffix!r} for {path}; "
            "expected '.json'"
        )
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError(f"{path} must contain an object at the top level")
    return load_cataloged_source(parsed)


def build_trusted_source_catalog(source_files: Iterable[Path] = ()) -> tuple[CatalogedSource, ...]:
    """Build the curated catalog by loading every given trusted-source config file. The
    caller resolves and passes in the files to load (mirrors
    ``grc_regulatory_intelligence.source_config.build_registry`` exactly); this module never
    assumes a repo layout itself."""
    return tuple(load_cataloged_source_file(path) for path in source_files)


def _require_str(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key!r} must be a non-empty string")
    return value


def _require_domains(data: Mapping[str, object]) -> list[object]:
    value = data.get("domains")
    if not isinstance(value, list) or not value:
        raise ValueError("'domains' must be a non-empty list")
    return value


def _load_source_type(raw: str) -> TrustedSourceType:
    try:
        return TrustedSourceType(raw)
    except ValueError as exc:
        valid = ", ".join(member.value for member in TrustedSourceType)
        raise ValueError(f"source_type {raw!r} is not one of: {valid}") from exc


def _load_domain(raw: object) -> KnowledgeDomain:
    if not isinstance(raw, str):
        raise ValueError(f"each domain must be a string, got {raw!r}")
    try:
        return KnowledgeDomain(raw)
    except ValueError as exc:
        valid = ", ".join(member.value for member in KnowledgeDomain)
        raise ValueError(f"domain {raw!r} is not one of: {valid}") from exc
