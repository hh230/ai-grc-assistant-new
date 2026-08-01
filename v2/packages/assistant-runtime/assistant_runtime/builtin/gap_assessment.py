"""The **Gap Assessment** capability — the flagship of "the system knows *my* company".

It is the composite that only became possible once the platform had both **inter-step context**
(ADR 0051) and **runtime per-tenant knowledge** (roadmap P1): it puts the framework's *required*
controls next to the customer's *actual* evidence and computes where the two do not meet — a real
gap analysis, not a catalog listing.

Steps (gather → gather → synthesise):

- `identify_controls` → **`framework_control_library`**: the ISO 27001 controls in scope (what the
  framework *requires*), cited by control id.
- `gather_evidence` → **`local_search`**: the customer's own ingested evidence for the scope (what
  the organization *actually has*), tenant-scoped and cited — the reason this is about *your*
  company, not ISO in the abstract.
- `compute_gap` → **`generate_text`**: reads the required controls *and* the customer evidence above
  (ADR 0051) and reports which controls are covered by evidence and which are **gaps**.

Tools are named by registry name only (`tool_names`); the capability imports no tool package.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mission_engine import Plan, PlanStep
from pipeline_contracts import TenantContext

from assistant_runtime.builtin.tool_names import (
    CONTROL_LIBRARY_TOOL,
    GENERATE_TEXT_TOOL,
    LOCAL_SEARCH_TOOL,
)
from assistant_runtime.capability import Capability
from assistant_runtime.mission_catalog import MissionType

GAP_ASSESSMENT_MISSION_ID = "gap_assessment"
GAP_ASSESSMENT_CAPABILITY_ID = "gap_assessment"

# Domain steps paired with (tool, query): required controls + the customer's evidence, then a
# synthesis that computes coverage vs. gaps from both (ADR 0051).
_STEPS: tuple[tuple[str, str, str], ...] = (
    ("Identify applicable controls", CONTROL_LIBRARY_TOOL, "{scope}"),
    ("Gather supporting evidence", LOCAL_SEARCH_TOOL, "{scope} evidence implemented controls"),
    ("Compute coverage and gaps", GENERATE_TEXT_TOOL,
     "Using the required controls and the evidence above, list which controls are covered by "
     "evidence and which are GAPS (no supporting evidence) for {scope}."),
)


def build_gap_assessment_plan(
    inputs: Mapping[str, Any], tenant: TenantContext
) -> tuple[str, Plan]:
    """`(inputs, tenant) → (goal, Plan)`: a composite, read-only plan — the required controls, the
    customer's evidence, then a coverage-vs-gap synthesis over both (ADR 0051). No consequential
    step → no gate."""
    scope = str(inputs.get("request", "")).strip() or "the requested scope"
    goal = f"gap assessment: {scope}"
    plan = Plan(
        steps=tuple(
            PlanStep(description=name, instruction=query.format(scope=scope), tool=tool)
            for name, tool, query in _STEPS
        )
    )
    return goal, plan


GAP_ASSESSMENT_MISSION_TYPE = MissionType(
    id=GAP_ASSESSMENT_MISSION_ID, plan_factory=build_gap_assessment_plan
)

GAP_ASSESSMENT_CAPABILITY = Capability(
    id=GAP_ASSESSMENT_CAPABILITY_ID,
    name="Gap Assessment",
    description=(
        "Assess which ISO 27001 controls for a scope are covered by your own evidence and which "
        "are gaps, grounded in your ingested documents, as a mission."
    ),
    input_schema=("request",),
    resolver=GAP_ASSESSMENT_MISSION_ID,
)
