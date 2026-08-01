"""The Framework Library domain — compliance frameworks represented as **data** (CLAUDE.md §13).

These are pure, immutable dataclasses with no dependency on a database, an LLM, or a framework. A
`Framework` is a versioned catalog of `Control`s; the shape mirrors the repo's existing framework
definition schema (`frameworks/iso-27001/2022/definition.json`) so V1 seed data and V2 bundled data
load identically. Lookups (by code, by theme, by title keyword) live here as pure methods — the tool
(`tool.py`) only formats their results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline_contracts import dataclass_dict


@dataclass(frozen=True)
class Requirement:
    """A control's stated requirement. `text` is empty in the bundled full catalog (the verbatim
    normative text is copyright and is the Pipeline Tool's grounded-retrieval job, ADR 0050)."""

    code: str = ""
    text: str = ""

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class EvidenceExpectation:
    """What evidence would demonstrate the control operates. Optional; empty in the full catalog."""

    description: str = ""

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class Control:
    """One control in a framework: a stable id, its `code` (`A.8.5`), a human `title`, and its
    `domain` (the framework's theme, e.g. `Technological`). `requirements` and
    `evidence_expectations` are optional enrichment (populated in seed data, empty in the bundled
    full catalog)."""

    id: str
    code: str
    title: str
    domain: str = ""
    requirements: tuple[Requirement, ...] = ()
    evidence_expectations: tuple[EvidenceExpectation, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)

    def matches_keyword(self, keyword: str) -> bool:
        """Case-insensitive substring match over code and title — the tool's keyword search."""
        needle = keyword.strip().lower()
        return needle in self.code.lower() or needle in self.title.lower()


@dataclass(frozen=True)
class Framework:
    """A versioned compliance framework as data (CLAUDE.md §13). Referenced by a stable id
    (`framework:iso_27001`), never a magic string in control flow."""

    id: str
    name: str
    version: str = ""
    region: str = ""
    languages: tuple[str, ...] = ()
    controls: tuple[Control, ...] = field(default_factory=tuple)

    def get(self, code: str) -> Control | None:
        """Exact control lookup by code (case-insensitive) — e.g. `A.8.5`."""
        wanted = code.strip().lower()
        for control in self.controls:
            if control.code.lower() == wanted:
                return control
        return None

    def by_domain(self, domain: str) -> tuple[Control, ...]:
        """All controls in a theme/domain (case-insensitive) — e.g. `Technological`."""
        wanted = domain.strip().lower()
        return tuple(c for c in self.controls if c.domain.lower() == wanted)

    def search(self, keyword: str) -> tuple[Control, ...]:
        """All controls whose code or title contains `keyword` (case-insensitive)."""
        if not keyword.strip():
            return ()
        return tuple(c for c in self.controls if c.matches_keyword(keyword))

    @property
    def domains(self) -> tuple[str, ...]:
        """The distinct themes present, in first-seen order."""
        seen: dict[str, None] = {}
        for control in self.controls:
            if control.domain and control.domain not in seen:
                seen[control.domain] = None
        return tuple(seen)

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)
