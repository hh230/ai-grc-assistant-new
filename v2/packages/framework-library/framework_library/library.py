"""`FrameworkLibrary` — loads compliance frameworks from **data files** and resolves them.

This is the heart of "frameworks are data, not code" (CLAUDE.md §13): a framework enters the system
by being a JSON file in the bundled `data/` directory (or any caller-supplied path), never by code.
Adding NIST / CIS / PCI / SOC2 is dropping in a file — `from_bundled()` discovers it automatically.
The loader translates the raw JSON (the repo's established definition schema) into the pure domain
models at the boundary (DDD anti-corruption, CLAUDE.md §15) so malformed input fails loud here, not
deep in the tool.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from framework_library.errors import FrameworkNotFound, InvalidFrameworkDefinition
from framework_library.models import (
    Control,
    EvidenceExpectation,
    Framework,
    Requirement,
)

_DATA_DIR = Path(__file__).parent / "data"


def _require(data: dict[str, Any], key: str, source: str) -> Any:
    if key not in data:
        raise InvalidFrameworkDefinition(f"{source}: missing required field {key!r}")
    return data[key]


def _control_from_dict(data: dict[str, Any], source: str) -> Control:
    return Control(
        id=str(_require(data, "id", source)),
        code=str(_require(data, "code", source)),
        title=str(_require(data, "title", source)),
        domain=str(data.get("domain", "")),
        requirements=tuple(
            Requirement(code=str(r.get("code", "")), text=str(r.get("text", "")))
            for r in data.get("requirements", ())
        ),
        evidence_expectations=tuple(
            EvidenceExpectation(description=str(e.get("description", "")))
            for e in data.get("evidence_expectations", ())
        ),
    )


def framework_from_dict(data: dict[str, Any], *, source: str = "<dict>") -> Framework:
    """Translate a raw framework definition (the repo's `definition.json` schema) into a
    `Framework`. Raises `InvalidFrameworkDefinition` on a missing id/name or malformed control."""
    controls_raw = _require(data, "controls", source)
    if not isinstance(controls_raw, list):
        raise InvalidFrameworkDefinition(f"{source}: 'controls' must be a list")
    return Framework(
        id=str(_require(data, "id", source)),
        name=str(_require(data, "name", source)),
        version=str(data.get("version", "")),
        region=str(data.get("region", "")),
        languages=tuple(str(lang) for lang in data.get("languages", ())),
        controls=tuple(_control_from_dict(c, source) for c in controls_raw),
    )


def framework_from_file(path: Path) -> Framework:
    """Load and parse one framework definition file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidFrameworkDefinition(f"{path.name}: not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise InvalidFrameworkDefinition(f"{path.name}: top level must be an object")
    return framework_from_dict(raw, source=path.name)


class FrameworkLibrary:
    """An immutable, in-memory catalog of loaded `Framework`s, keyed by framework id. Pure: it
    holds data and resolves it; it performs no I/O after construction and knows nothing of tenants,
    tools, or missions (those are the tool's concern)."""

    def __init__(self, frameworks: Iterable[Framework]) -> None:
        self._by_id: dict[str, Framework] = {}
        for framework in frameworks:
            self._by_id[framework.id] = framework

    @classmethod
    def from_files(cls, paths: Iterable[Path]) -> FrameworkLibrary:
        return cls(framework_from_file(path) for path in paths)

    @classmethod
    def from_dir(cls, directory: Path) -> FrameworkLibrary:
        """Load every `*.json` framework definition in a directory (sorted for determinism)."""
        return cls.from_files(sorted(directory.glob("*.json")))

    @classmethod
    def from_bundled(cls) -> FrameworkLibrary:
        """The default library: every framework data file bundled with the package. Adding a
        framework is dropping a file into `data/` — no code change (CLAUDE.md §13)."""
        return cls.from_dir(_DATA_DIR)

    @property
    def framework_ids(self) -> tuple[str, ...]:
        return tuple(self._by_id)

    def has(self, framework_id: str) -> bool:
        return framework_id in self._by_id

    def get(self, framework_id: str) -> Framework:
        """Resolve a framework by id, or fail loud with the available ids."""
        framework = self._by_id.get(framework_id)
        if framework is None:
            raise FrameworkNotFound(framework_id, self.framework_ids)
        return framework
