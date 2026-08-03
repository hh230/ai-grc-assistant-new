"""The **Governance Plan** capability — the AI Governance Planning Engine's flagship output (ADR
0066 §3): turns a concluded Governance Discovery session into a real, versioned, trackable
transformation plan.

Steps (resolve → gather → draft → finalize):

- `resolve_applicability` → **`org_applicability`**: the concluded session's one-shot analysis
  (frameworks, maturity, capacity, gaps, plan seeds) — a pure read, the Mission never re-evaluates
  rules (ADR 0066 §2).
- `gather_control_library` → **`framework_control_library`**: the controls behind the identified
  frameworks, for the drafting step's grounding.
- `draft_plan` → **`governance_plan_draft`**: computes due dates and drafts the bounded LLM prose
  (executive brief, per-gap business impact, per-item rationale/objective/outcome/risk) — the
  reviewable content, not yet persisted.
- `finalize_plan` → **`governance_plan_finalize`**, **consequential**: persists the approved draft
  as a new immutable plan version (ADR 0066 §3.1), superseding the tenant's previous active plan.

The draft/finalize split (not one combined step) exists because the Mission Engine's approval gate
pauses BEFORE a consequential step runs — the reviewable content has to already exist by the time
a human is asked to approve it. Tools are named by registry name only (`tool_names`); the
capability imports no tool package.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mission_engine import Plan, PlanStep
from pipeline_contracts import TenantContext

from assistant_runtime.builtin.tool_names import (
    CONTROL_LIBRARY_TOOL,
    ORG_APPLICABILITY_TOOL,
    PLAN_DRAFT_TOOL,
    PLAN_FINALIZE_TOOL,
)
from assistant_runtime.capability import Capability
from assistant_runtime.mission_catalog import MissionType

GENERATE_GOVERNANCE_PLAN_MISSION_ID = "generate_governance_plan"
GENERATE_GOVERNANCE_PLAN_CAPABILITY_ID = "generate_governance_plan"


def build_generate_governance_plan_plan(
    inputs: Mapping[str, Any], tenant: TenantContext
) -> tuple[str, Plan]:
    """`(inputs, tenant) → (goal, Plan)`: `inputs["request"]` carries the concluded Discovery
    session id this plan is generated from — every builtin capability's plan_factory reads its one
    opaque input string from this same key (the REST host maps its `scope` field to `inputs["request"]`
    uniformly, `grc_api/adapters.py`'s `CatalogDefinitionProvider.define`; there is no
    capability-specific input key). One consequential step (`finalize_plan`) → one approval gate
    (ADR 0044), sitting after the content exists to review."""
    session_id = str(inputs.get("request", "")).strip()
    goal = f"generate governance plan: {session_id}"
    plan = Plan(
        steps=(
            PlanStep(
                description="Resolve the organization's applicability analysis",
                instruction=session_id,
                tool=ORG_APPLICABILITY_TOOL,
            ),
            PlanStep(
                description="Gather the relevant framework control library",
                instruction="ISO 27001 CIS NIST CSF security controls",
                tool=CONTROL_LIBRARY_TOOL,
            ),
            PlanStep(
                description="Draft the governance plan for review",
                instruction=session_id,
                tool=PLAN_DRAFT_TOOL,
            ),
            PlanStep(
                description="Finalize and persist the approved governance plan",
                instruction=session_id,
                consequential=True,
                tool=PLAN_FINALIZE_TOOL,
            ),
        )
    )
    return goal, plan


GENERATE_GOVERNANCE_PLAN_MISSION_TYPE = MissionType(
    id=GENERATE_GOVERNANCE_PLAN_MISSION_ID, plan_factory=build_generate_governance_plan_plan
)

GENERATE_GOVERNANCE_PLAN_CAPABILITY = Capability(
    id=GENERATE_GOVERNANCE_PLAN_CAPABILITY_ID,
    name="Governance Plan",
    description=(
        "Turn a concluded Governance Discovery session into a real, versioned transformation "
        "plan — grounded in your organization's own answers, as a mission with a human approval "
        "gate before anything is finalized."
    ),
    input_schema=("request",),
    resolver=GENERATE_GOVERNANCE_PLAN_MISSION_ID,
)
