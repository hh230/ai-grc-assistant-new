"""Rasheed V2 **AI GRC Assistant** — the product-layer runtime (ADR 0046).

The Assistant is the gateway that turns a user's request into the *right* Mission and drives it
through the **frozen** Core (`MissionRuntime`). This package is the runtime **mechanism** — it adds
no capability to the Core and changes nothing in it.

**Slice 2 (Capability & Mission Catalog)** ships exactly the wiring:

- `Capability` + `CapabilityCatalog` — the product-facing registry (*what* the Assistant can do).
- `MissionType` + `MissionCatalog` — the execution registry (*how* each is built: a plan factory
  `(inputs, tenant) → (goal, Plan)`).
- `IntentRecognizer` (port) + `KeywordIntentRecognizer` (reference, no LLM) + `CapabilityIntent` —
  layer 1 of selection: the LLM *suggests*.
- `CapabilitySelector` — layer 2: deterministic *decision* (exists? → it; else → fallback).
- `MissionDriver` (port) — the one seam into the Core; `MissionRuntime` satisfies it structurally.
- `AssistantRuntime` + `AssistantResponse` — the thin composition root: `handle(request, tenant)`.

Not in Slice 2 (later slices): sessions/conversations, real LLM, tools, retrieval, streaming,
API/UI, multi-Mission orchestration.
"""

from assistant_runtime.builtin import (
    AI_GRC_ASSISTANT_CAPABILITY,
    RISK_ASSESSMENT_CAPABILITY,
    RISK_ASSESSMENT_MISSION_TYPE,
    SIMPLE_QUESTION_MISSION_TYPE,
    build_assistant,
)
from assistant_runtime.capability import Capability
from assistant_runtime.capability_catalog import CapabilityCatalog
from assistant_runtime.errors import (
    AssistantError,
    FallbackCapabilityMissing,
    UnknownMissionType,
)
from assistant_runtime.intent import (
    CapabilityIntent,
    IntentRecognizer,
    KeywordIntentRecognizer,
)
from assistant_runtime.mission_catalog import MissionCatalog, MissionType, PlanFactory
from assistant_runtime.ports import MissionDriver
from assistant_runtime.runtime import AssistantResponse, AssistantRuntime
from assistant_runtime.selector import CapabilitySelector

__all__ = [
    # capability catalog (product-facing)
    "Capability",
    "CapabilityCatalog",
    # mission catalog (execution)
    "MissionType",
    "MissionCatalog",
    "PlanFactory",
    # selection: layer 1 (suggest) + layer 2 (decide)
    "CapabilityIntent",
    "IntentRecognizer",
    "KeywordIntentRecognizer",
    "CapabilitySelector",
    # the one seam into the frozen Core
    "MissionDriver",
    # composition root
    "AssistantRuntime",
    "AssistantResponse",
    # built-in capabilities + one-call assembler
    "build_assistant",
    "AI_GRC_ASSISTANT_CAPABILITY",
    "SIMPLE_QUESTION_MISSION_TYPE",
    "RISK_ASSESSMENT_CAPABILITY",
    "RISK_ASSESSMENT_MISSION_TYPE",
    # errors
    "AssistantError",
    "FallbackCapabilityMissing",
    "UnknownMissionType",
]
