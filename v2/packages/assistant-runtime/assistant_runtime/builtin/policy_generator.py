"""The **Policy Generator** capability — real and **coherent** (ADR 0051 → connected).

A GRC policy must align to control requirements, so this is a **composite** that gathers then
synthesises — the draft is written *from* the gathered material (ADR 0051 inter-step context):

- `identify_controls` → **`framework_control_library`**: the ISO 27001 controls in scope for the
  topic (deterministic, cited by control id).
- `gather_guidance` → **`local_search`**: guidance from the **customer's own ingested data ∪
  global knowledge**, tenant-scoped and cited (product roadmap P1 integration).
- `draft_policy` → **`generate_text`**: the policy draft, generated *from* the identified controls +
  guidance above (the tool reads the prior steps' output as context, ADR 0051), with clear sections.

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

POLICY_GENERATOR_MISSION_ID = "policy_generator"
POLICY_GENERATOR_CAPABILITY_ID = "policy_generator"

# Domain steps paired with (tool, query): a controls lookup + a tenant-scoped search gather (reads
# the customer's data) then a synthesis that builds on them (ADR 0051).
_STEPS: tuple[tuple[str, str, str], ...] = (
    ("Identify relevant controls", CONTROL_LIBRARY_TOOL, "{topic}"),
    ("Gather policy guidance", LOCAL_SEARCH_TOOL, "{topic} policy guidance"),
    ("Draft the policy", GENERATE_TEXT_TOOL,
     "Using the controls and guidance above, draft a {topic} policy with clear sections."),
)


def build_policy_generator_plan(
    inputs: Mapping[str, Any], tenant: TenantContext
) -> tuple[str, Plan]:
    """`(inputs, tenant) → (goal, Plan)`: a composite, read-only plan — controls + grounded
    guidance, then a policy draft synthesised from them (ADR 0051). No consequential step → no
    gate."""
    topic = str(inputs.get("request", "")).strip() or "the requested topic"
    goal = f"policy generation: {topic}"
    plan = Plan(
        steps=tuple(
            PlanStep(description=name, instruction=query.format(topic=topic), tool=tool)
            for name, tool, query in _STEPS
        )
    )
    return goal, plan


POLICY_GENERATOR_MISSION_TYPE = MissionType(
    id=POLICY_GENERATOR_MISSION_ID, plan_factory=build_policy_generator_plan
)

POLICY_GENERATOR_CAPABILITY = Capability(
    id=POLICY_GENERATOR_CAPABILITY_ID,
    name="Policy Generator",
    description=(
        "Draft a GRC policy for a topic, aligned to the applicable ISO 27001 controls and grounded "
        "in the knowledge base, as a mission."
    ),
    input_schema=("request",),
    resolver=POLICY_GENERATOR_MISSION_ID,
)
