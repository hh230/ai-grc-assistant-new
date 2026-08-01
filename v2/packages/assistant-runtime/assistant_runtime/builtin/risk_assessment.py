"""The **Risk Assessment** capability — a *composite*, **real and coherent** (ADR 0047 → real; ADR
0051 → connected). It keeps its domain shape (`collect_context → assess_risk → generate_report`) and
now **chains**: a grounded gather step produces the evidence, and the later steps **synthesise from
it** (ADR 0051 inter-step context) — so the report is written *from* the assessment, which is
written *from* the evidence, not three disconnected artifacts.

Steps:

- `collect_context` → **`local_search`**: retrieves the controls and evidence relevant to the
  subject — from the **customer's own ingested data ∪ global knowledge**, tenant-scoped and cited
  (product roadmap P1 integration). Search, not `run_pipeline`, so the customer's uploaded documents
  are actually retrieved (the pipeline's framework-profile routing would exclude them).
- `assess_risk` → **`generate_text`**: the GRC risk assessment, generated *from* the collected
  evidence (the tool reads the prior step's output as context, ADR 0051).
- `generate_report` → **`generate_text`**: the report, generated *from* the evidence + the
  assessment.

Design notes: domain step names are stable (ADR 0047); tools are named by **registry name only**
(`tool_names`, guarded against drift by `grc-assistant`), so the capability imports no tool package;
the Capability carries no detection field (ADR 0047).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mission_engine import Plan, PlanStep
from pipeline_contracts import TenantContext

from assistant_runtime.builtin.tool_names import GENERATE_TEXT_TOOL, LOCAL_SEARCH_TOOL
from assistant_runtime.capability import Capability
from assistant_runtime.mission_catalog import MissionType

RISK_ASSESSMENT_MISSION_ID = "risk_assessment"
RISK_ASSESSMENT_CAPABILITY_ID = "risk_assessment"

__all__ = [
    "LOCAL_SEARCH_TOOL",
    "GENERATE_TEXT_TOOL",
    "RISK_ASSESSMENT_MISSION_ID",
    "RISK_ASSESSMENT_CAPABILITY_ID",
    "RISK_ASSESSMENT_MISSION_TYPE",
    "RISK_ASSESSMENT_CAPABILITY",
    "build_risk_assessment_plan",
]

# Domain steps paired with (tool, query): a tenant-scoped search gather (local_search, reads the
# customer's data) then two syntheses (generate_text) that build on it (ADR 0051).
_STEPS: tuple[tuple[str, str, str], ...] = (
    ("Collect relevant context", LOCAL_SEARCH_TOOL, "controls and evidence relevant to {subject}"),
    ("Assess the risk", GENERATE_TEXT_TOOL,
     "Using the evidence above, assess the GRC risk of {subject}: likelihood, impact, gaps."),
    ("Write the risk report", GENERATE_TEXT_TOOL,
     "Using the evidence and assessment above, write a risk report with remediation for {subject}"),
)


def build_risk_assessment_plan(
    inputs: Mapping[str, Any], tenant: TenantContext
) -> tuple[str, Plan]:
    """`(inputs, tenant) → (goal, Plan)`: a composite, read-only plan — a grounded gather then two
    syntheses that build on it (ADR 0051). No consequential step → no human gate."""
    subject = str(inputs.get("request", "")).strip() or "the requested subject"
    goal = f"risk assessment: {subject}"
    plan = Plan(
        steps=tuple(
            PlanStep(description=name, instruction=query.format(subject=subject), tool=tool)
            for name, tool, query in _STEPS
        )
    )
    return goal, plan


RISK_ASSESSMENT_MISSION_TYPE = MissionType(
    id=RISK_ASSESSMENT_MISSION_ID, plan_factory=build_risk_assessment_plan
)

RISK_ASSESSMENT_CAPABILITY = Capability(
    id=RISK_ASSESSMENT_CAPABILITY_ID,
    name="Risk Assessment",
    description="Assess the risk of a subject (asset, vendor, system, or scenario) as a mission.",
    input_schema=("request",),
    resolver=RISK_ASSESSMENT_MISSION_ID,
)
