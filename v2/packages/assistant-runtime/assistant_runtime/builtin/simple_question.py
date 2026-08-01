"""The **first built-in capability** — the AI GRC Assistant's *Simple Question* (ADR 0046, Slice 3).

This is the smallest real capability that proves the whole loop
`User → AssistantRuntime → Capability → Mission → MissionRuntime → Response` works front to back. It
is chosen first *because* it needs **no tools, no complex plan, no human approval, no multiple
Missions** — a Simple Question is a single read-only Mission step.

- `SIMPLE_QUESTION_MISSION_TYPE` — the Mission type: a plan factory that turns the request into a
  one-step, read-only `Plan` (the `simple` mission of ADR 0042 §11). The step is executed by the
  `ExecutionPort` backing the injected Core (the reference `EchoExecutor` until the real Pipeline
  executor lands) — so no real answer is produced yet, only the round-trip is proven.
- `AI_GRC_ASSISTANT_CAPABILITY` — the product-facing capability the user reaches: "ask the AI GRC
  Assistant a question." It resolves to the Simple Question Mission type. It is also the natural
  **fallback**: when intent recognition finds no better match, the request is simply *asked*.

GRC capabilities (Risk Assessment, Vendor Review, …) are added later, one at a time, on this tested
foundation — each a new Capability + Mission type, not new plumbing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mission_engine import Plan, single_step_plan
from pipeline_contracts import TenantContext

from assistant_runtime.capability import Capability
from assistant_runtime.mission_catalog import MissionType

# Stable ids. The capability id is the product-facing "ask the assistant"; the mission type id names
# the executable unit. They live in different catalogs, so sharing a theme is fine, not a collision.
SIMPLE_QUESTION_MISSION_ID = "simple_question"
AI_GRC_ASSISTANT_CAPABILITY_ID = "ask"


def build_simple_question_plan(
    inputs: Mapping[str, Any], tenant: TenantContext
) -> tuple[str, Plan]:
    """`(inputs, tenant) → (goal, Plan)`: the request becomes the mission's goal and its single
    read-only step. Empty input degrades to a neutral question rather than an empty plan."""
    request = str(inputs.get("request", "")).strip() or "answer the question"
    return request, single_step_plan(request, description="Answer the question")


SIMPLE_QUESTION_MISSION_TYPE = MissionType(
    id=SIMPLE_QUESTION_MISSION_ID, plan_factory=build_simple_question_plan
)

AI_GRC_ASSISTANT_CAPABILITY = Capability(
    id=AI_GRC_ASSISTANT_CAPABILITY_ID,
    name="AI GRC Assistant",
    description="Ask the AI GRC Assistant a question; it answers as a Simple Question mission.",
    input_schema=("request",),
    resolver=SIMPLE_QUESTION_MISSION_ID,
)
