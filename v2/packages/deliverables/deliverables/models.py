"""The structured deliverable models (product roadmap P3).

A **Deliverable** is what a completed Mission's raw step outputs become for a customer: a
structured, cited, exportable document — not a wall of text. Everything here is a pure, immutable
object; assembly lives in `build.py`, rendering in `render.py`.

The **GapMatrix** is the flagship structured output: the framework's *required* controls next to
whether the customer's *evidence* covers each — `control ↔ status ↔ evidence` — derived
deterministically from the mission and the framework catalog (no LLM in the structure itself).
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline_contracts import dataclass_dict


@dataclass(frozen=True)
class Section:
    """One section of a deliverable: a heading, its body, and the provenance (`citations`) and
    `confidence` that make it auditable — every claim traces to its sources."""

    heading: str
    body: str
    citations: tuple[str, ...] = ()
    confidence: float | None = None

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class Deliverable:
    """A structured, exportable GRC deliverable assembled from a completed mission. Carries the
    mission's goal, tenant, and generation time for the audit trail (§19)."""

    title: str
    goal: str
    tenant_id: str
    generated_at: str
    sections: tuple[Section, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class GapRow:
    """One control's coverage: the required control, whether the customer's evidence covers it, and
    the evidence sources that support it (empty when it is a gap)."""

    control_code: str
    control_title: str
    covered: bool
    evidence: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return "covered" if self.covered else "gap"

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self, extra={"status": self.status})


@dataclass(frozen=True)
class GapMatrix:
    """An **evidence-mapping** matrix (`control ↔ status ↔ evidence`) for a scope of a framework:
    which required controls have *supporting evidence in the customer's corpus*, and which are gaps.
    `coverage` is the share with supporting evidence — an **evidence** figure, **not** a compliance
    attestation (the nuanced assessment is the mission's own gap synthesis)."""

    framework: str
    scope: str
    rows: tuple[GapRow, ...] = ()

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def covered_count(self) -> int:
        return sum(1 for r in self.rows if r.covered)

    @property
    def gaps(self) -> tuple[GapRow, ...]:
        return tuple(r for r in self.rows if not r.covered)

    @property
    def coverage(self) -> float:
        return round(self.covered_count / self.total, 4) if self.total else 0.0

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(
            self,
            extra={
                "total": self.total,
                "covered_count": self.covered_count,
                "coverage": self.coverage,
            },
        )
