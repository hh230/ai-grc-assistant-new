"""The **ISO Controls** capability — the first capability backed by a *real* GRC tool.

Where Simple Question routes to the default tool (grounded RAG) and Risk Assessment is still a
placeholder shape, ISO Controls resolves to a Mission whose step is executed by the **Framework
Library tool** (`framework-library`, ADR 0050): a deterministic lookup of the ISO/IEC 27001:2022
Annex A catalog. It is the smallest *real, non-Echo* GRC capability — the user asks for ISO controls
by scope (a theme like "Technological", a code like "A.8.5", or a title keyword like "access"), and
the Mission returns the actual controls, with their control ids as provenance.

The capability names its tool by **registry name only** (`CONTROL_LIBRARY_TOOL`) — the seam of ADR
0048's `PlanStep.tool`. The capability layer never imports a tool implementation: the composition
root (`grc-assistant`) registers a tool under that name, and its test guards the name against drift.
Swapping the ISO library implementation changes nothing here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mission_engine import Plan, PlanStep
from pipeline_contracts import TenantContext

from assistant_runtime.builtin.tool_names import CONTROL_LIBRARY_TOOL
from assistant_runtime.capability import Capability
from assistant_runtime.mission_catalog import MissionType

ISO_CONTROLS_MISSION_ID = "iso_controls"
ISO_CONTROLS_CAPABILITY_ID = "iso_controls"

# The registered name of the Framework Library tool this capability routes its step to (ADR 0048)
# is the single-sourced `CONTROL_LIBRARY_TOOL` (see `tool_names`), re-exported here for callers.
__all__ = [
    "CONTROL_LIBRARY_TOOL",
    "ISO_CONTROLS_MISSION_ID",
    "ISO_CONTROLS_CAPABILITY_ID",
    "ISO_CONTROLS_MISSION_TYPE",
    "ISO_CONTROLS_CAPABILITY",
    "build_iso_controls_plan",
]


def build_iso_controls_plan(
    inputs: Mapping[str, Any], tenant: TenantContext
) -> tuple[str, Plan]:
    """`(inputs, tenant) → (goal, Plan)`: a single read-only step that looks up ISO 27001 controls
    for the requested scope via the Framework Library tool. The scope is passed through as the step
    `instruction` (the tool reads it as a code / theme / keyword; empty ⇒ the whole catalog). No
    consequential step ⇒ no human gate."""
    scope = str(inputs.get("request", "")).strip()
    goal = f"ISO 27001 controls: {scope or 'all controls'}"
    plan = Plan(
        steps=(
            PlanStep(
                description="List the ISO 27001 controls in scope",
                instruction=scope,
                tool=CONTROL_LIBRARY_TOOL,
            ),
        )
    )
    return goal, plan


ISO_CONTROLS_MISSION_TYPE = MissionType(
    id=ISO_CONTROLS_MISSION_ID, plan_factory=build_iso_controls_plan
)

ISO_CONTROLS_CAPABILITY = Capability(
    id=ISO_CONTROLS_CAPABILITY_ID,
    name="ISO Controls",
    description=(
        "Look up the ISO/IEC 27001:2022 controls relevant to a scope (theme, control code, or "
        "keyword) — grounded in the framework catalog, as a mission."
    ),
    input_schema=("request",),
    resolver=ISO_CONTROLS_MISSION_ID,
)
