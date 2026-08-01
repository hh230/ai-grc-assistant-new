"""Assemble structured deliverables from a completed Mission (product roadmap P3).

Pure functions: a `Mission` (and, for the gap matrix, a `FrameworkLibrary`) in, a structured value
object out. No I/O, no LLM, no Core dependency beyond reading the frozen `Mission`/`StepResult`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from framework_library import Control, FrameworkLibrary
from mission_engine import Mission

from deliverables.models import Deliverable, GapMatrix, GapRow, Section

_STOPWORDS = frozenset(
    {"and", "for", "the", "with", "other", "associated", "information", "management", "use", "of"}
)


def _humanize(name: str) -> str:
    return name.replace("_", " ").strip().title() or "Step"


def build_deliverable(
    mission: Mission,
    *,
    title: str,
    now: datetime | None = None,
) -> Deliverable:
    """Turn a completed mission into a structured, cited deliverable: each recorded step becomes a
    `Section` headed by its (domain) step description, with the step's `source_ids` as citations and
    its confidence carried through — an audit-ready document, not raw text."""
    generated_at = (now or datetime.now(tz=timezone.utc)).isoformat()
    steps = mission.plan.steps if mission.plan is not None else ()
    sections: list[Section] = []
    for index, result in enumerate(mission.step_results):
        description = steps[index].description if index < len(steps) else ""
        sections.append(
            Section(
                heading=_humanize(description) if description else result.step_id,
                body=result.output,
                citations=tuple(result.source_ids),
                confidence=result.confidence,
            )
        )
    return Deliverable(
        title=title,
        goal=mission.goal,
        tenant_id=mission.tenant_id,
        generated_at=generated_at,
        sections=tuple(sections),
    )


def lexical_coverage(control: Control, evidence_text: str) -> bool:
    """The default, deterministic coverage heuristic: a control is *candidate-covered* when a
    significant word of its title appears in the gathered evidence. It is a lexical **first pass** —
    a transparent, testable baseline; the mission's own gap synthesis (an LLM step) gives the
    nuanced narrative, and a smarter classifier can be injected via `coverage`. Never overstated:
    the matrix says which controls have *supporting evidence*, not a legal attestation."""
    text = evidence_text.lower()
    words = (control.title.lower().replace(",", " ").replace("(", " ").replace(")", " ").split())
    significant = [w for w in words if len(w) > 3 and w not in _STOPWORDS]
    return any(w in text for w in significant)


def build_gap_matrix(
    mission: Mission,
    library: FrameworkLibrary,
    *,
    framework_id: str = "framework:iso_27001",
    controls_step: int = 0,
    evidence_step: int = 1,
    coverage: Callable[[Control, str], bool] = lexical_coverage,
) -> GapMatrix:
    """Build the `control ↔ status ↔ evidence` matrix from a Gap Assessment mission: the required
    controls (the `identify_controls` step's `source_ids`) against the customer's gathered evidence
    (the `gather_evidence` step's output). Each required control becomes a row marked *covered* or
    *gap* by `coverage`, with the evidence sources attached when covered."""
    results = mission.step_results
    controls_result = results[controls_step]
    evidence_result = results[evidence_step]
    framework = library.get(framework_id)
    by_id = {control.id: control for control in framework.controls}

    evidence_text = evidence_result.output
    evidence_sources = tuple(evidence_result.source_ids)
    rows: list[GapRow] = []
    for control_id in controls_result.source_ids:
        control = by_id.get(control_id)
        if control is None:
            continue
        covered = coverage(control, evidence_text)
        rows.append(
            GapRow(
                control_code=control.code,
                control_title=control.title,
                covered=covered,
                evidence=evidence_sources if covered else (),
            )
        )
    scope = mission.goal.split(":", 1)[-1].strip() if ":" in mission.goal else mission.goal
    return GapMatrix(framework=framework.name, scope=scope, rows=tuple(rows))
