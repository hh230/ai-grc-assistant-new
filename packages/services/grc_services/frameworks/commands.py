"""Commands for the Framework capability (frameworks are data, imported as definitions)."""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_domain.frameworks.value_objects import FrameworkControl
from grc_domain.shared.identifiers import FrameworkId

from ..shared.messages import Command


@dataclass(frozen=True, kw_only=True)
class ImportFramework(Command):
    framework_id: FrameworkId
    name: str
    version: str
    controls: tuple[FrameworkControl, ...]
    region: str | None = None
    languages: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, kw_only=True)
class PublishFramework(Command):
    framework_id: FrameworkId
    version: str


@dataclass(frozen=True, kw_only=True)
class DeprecateFramework(Command):
    framework_id: FrameworkId
    version: str
