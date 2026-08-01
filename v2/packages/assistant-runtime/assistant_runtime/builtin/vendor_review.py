"""The **Vendor Review** capability — real and **coherent** (ADR 0051 → connected).

A vendor review needs the supplier-management controls and a risk view of the vendor, and now the
assessment is written *from* the gathered material (ADR 0051 inter-step context):

- `identify_supplier_controls` → **`framework_control_library`**: the ISO 27001 supplier controls
  (A.5.19–A.5.23), by the `"supplier"` theme keyword — real, cited by control id.
- `gather_vendor_context` → **`local_search`**: the vendor's own uploaded evidence (SOC 2,
  questionnaire) and any relevant guidance — from the **customer's ingested data ∪ global
  knowledge**, tenant-scoped and cited (roadmap P1 integration). Once the tenant has uploaded
  the vendor's documents, this step retrieves them.
- `assess_vendor` → **`generate_text`**: the vendor risk assessment, generated *from* the supplier
  controls + the retrieved vendor evidence above (ADR 0051).

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

VENDOR_REVIEW_MISSION_ID = "vendor_review"
VENDOR_REVIEW_CAPABILITY_ID = "vendor_review"

# Domain steps paired with (tool, query): supplier controls + a tenant-scoped search gather (reads
# the vendor's uploaded evidence) then a synthesis that builds on them (ADR 0051).
_STEPS: tuple[tuple[str, str, str], ...] = (
    ("Identify supplier controls", CONTROL_LIBRARY_TOOL, "supplier"),
    ("Gather vendor context", LOCAL_SEARCH_TOOL, "vendor {vendor} security risk evidence"),
    ("Assess the vendor", GENERATE_TEXT_TOOL,
     "Using the supplier controls and considerations above, assess vendor {vendor}'s risk."),
)


def build_vendor_review_plan(
    inputs: Mapping[str, Any], tenant: TenantContext
) -> tuple[str, Plan]:
    """`(inputs, tenant) → (goal, Plan)`: a composite, read-only plan — supplier controls + grounded
    context, then a vendor assessment synthesised from them (ADR 0051). No consequential step → no
    gate."""
    vendor = str(inputs.get("request", "")).strip() or "the vendor"
    goal = f"vendor review: {vendor}"
    plan = Plan(
        steps=tuple(
            PlanStep(description=name, instruction=query.format(vendor=vendor), tool=tool)
            for name, tool, query in _STEPS
        )
    )
    return goal, plan


VENDOR_REVIEW_MISSION_TYPE = MissionType(
    id=VENDOR_REVIEW_MISSION_ID, plan_factory=build_vendor_review_plan
)

VENDOR_REVIEW_CAPABILITY = Capability(
    id=VENDOR_REVIEW_CAPABILITY_ID,
    name="Vendor Review",
    description=(
        "Review a vendor's security and compliance risk against the applicable supplier controls, "
        "grounded in the knowledge base, as a mission."
    ),
    input_schema=("request",),
    resolver=VENDOR_REVIEW_MISSION_ID,
)
