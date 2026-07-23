"""Built-in capabilities shipped with the AI GRC Assistant, and a default assembler (ADR 0046/0047).

Ships the built-in capabilities — *Simple Question* (the fallback, `simple_question.py`) and *Risk
Assessment* (the first composite, `risk_assessment.py`) — plus `build_assistant`, which wires a
ready `AssistantRuntime` over an injected `MissionRuntime`. GRC capabilities are added here one at a
time, without touching the runtime mechanism.

**Detection lives with the recognizer, never on a Capability** (ADR 0047 ruling). The reference
`KeywordIntentRecognizer`'s keyword → capability-id map is *recognizer config assembled here*; the
Capability records carry no keyword and no recognizer type. Replacing the recognizer with an LLM /
semantic / hybrid one is a change to `default_intent_recognizer` alone — no Capability moves.
"""

from __future__ import annotations

from assistant_runtime.builtin.gap_assessment import (
    GAP_ASSESSMENT_CAPABILITY,
    GAP_ASSESSMENT_CAPABILITY_ID,
    GAP_ASSESSMENT_MISSION_ID,
    GAP_ASSESSMENT_MISSION_TYPE,
    build_gap_assessment_plan,
)
from assistant_runtime.builtin.iso_controls import (
    ISO_CONTROLS_CAPABILITY,
    ISO_CONTROLS_CAPABILITY_ID,
    ISO_CONTROLS_MISSION_ID,
    ISO_CONTROLS_MISSION_TYPE,
    build_iso_controls_plan,
)
from assistant_runtime.builtin.policy_generator import (
    POLICY_GENERATOR_CAPABILITY,
    POLICY_GENERATOR_CAPABILITY_ID,
    POLICY_GENERATOR_MISSION_ID,
    POLICY_GENERATOR_MISSION_TYPE,
    build_policy_generator_plan,
)
from assistant_runtime.builtin.risk_assessment import (
    RISK_ASSESSMENT_CAPABILITY,
    RISK_ASSESSMENT_CAPABILITY_ID,
    RISK_ASSESSMENT_MISSION_ID,
    RISK_ASSESSMENT_MISSION_TYPE,
    build_risk_assessment_plan,
)
from assistant_runtime.builtin.simple_question import (
    AI_GRC_ASSISTANT_CAPABILITY,
    AI_GRC_ASSISTANT_CAPABILITY_ID,
    SIMPLE_QUESTION_MISSION_ID,
    SIMPLE_QUESTION_MISSION_TYPE,
    build_simple_question_plan,
)
from assistant_runtime.builtin.vendor_review import (
    VENDOR_REVIEW_CAPABILITY,
    VENDOR_REVIEW_CAPABILITY_ID,
    VENDOR_REVIEW_MISSION_ID,
    VENDOR_REVIEW_MISSION_TYPE,
    build_vendor_review_plan,
)
from assistant_runtime.capability_catalog import CapabilityCatalog
from assistant_runtime.intent import KeywordIntentRecognizer
from assistant_runtime.mission_catalog import MissionCatalog
from assistant_runtime.ports import MissionDriver
from assistant_runtime.runtime import AssistantRuntime

# The capability every unmatched request falls back to: "just ask the AI GRC Assistant".
FALLBACK_CAPABILITY_ID = AI_GRC_ASSISTANT_CAPABILITY_ID


def default_capability_catalog() -> CapabilityCatalog:
    """The Capability Catalog with the built-ins: the AI GRC Assistant + Risk Assessment + ISO
    Controls."""
    return CapabilityCatalog(
        [
            AI_GRC_ASSISTANT_CAPABILITY,
            RISK_ASSESSMENT_CAPABILITY,
            ISO_CONTROLS_CAPABILITY,
            POLICY_GENERATOR_CAPABILITY,
            VENDOR_REVIEW_CAPABILITY,
            GAP_ASSESSMENT_CAPABILITY,
        ]
    )


def default_mission_catalog() -> MissionCatalog:
    """The Mission Catalog with the built-in Mission types: Simple Question + Risk Assessment + ISO
    Controls + Policy Generator + Vendor Review."""
    return MissionCatalog(
        [
            SIMPLE_QUESTION_MISSION_TYPE,
            RISK_ASSESSMENT_MISSION_TYPE,
            ISO_CONTROLS_MISSION_TYPE,
            POLICY_GENERATOR_MISSION_TYPE,
            VENDOR_REVIEW_MISSION_TYPE,
            GAP_ASSESSMENT_MISSION_TYPE,
        ]
    )


def default_intent_recognizer() -> KeywordIntentRecognizer:
    """The reference recognizer (NO LLM). **This is recognizer config, not capability data**
    (ADR 0047): the keyword → capability-id map lives here and only here. It emits a capability
    *intent* (`gap` → `gap_assessment`, `risk` → `risk_assessment`, `iso` → `iso_controls`,
    `policy` → `policy_generator`, `vendor` → `vendor_review`); first hit wins (so `risk` before
    `vendor` keeps "risk of vendor X" on Risk Assessment), unmatched → fallback to `ask`. A real
    LLM / semantic recognizer implements the same port and replaces this function alone."""
    return KeywordIntentRecognizer(
        {
            "gap": GAP_ASSESSMENT_CAPABILITY_ID,
            "risk": RISK_ASSESSMENT_CAPABILITY_ID,
            "iso": ISO_CONTROLS_CAPABILITY_ID,
            "policy": POLICY_GENERATOR_CAPABILITY_ID,
            "vendor": VENDOR_REVIEW_CAPABILITY_ID,
        }
    )


def build_assistant(mission_runtime: MissionDriver) -> AssistantRuntime:
    """Assemble a ready `AssistantRuntime` over an injected `MissionRuntime` (any `MissionDriver`):
    the built-in catalogs + the reference recognizer, with the AI GRC Assistant as the fallback. The
    one-call entry a delivery app (or a test) uses to get a working assistant."""
    return AssistantRuntime(
        missions=mission_runtime,
        capabilities=default_capability_catalog(),
        mission_catalog=default_mission_catalog(),
        intent=default_intent_recognizer(),
        fallback_capability_id=FALLBACK_CAPABILITY_ID,
    )


__all__ = [
    "AI_GRC_ASSISTANT_CAPABILITY",
    "AI_GRC_ASSISTANT_CAPABILITY_ID",
    "SIMPLE_QUESTION_MISSION_TYPE",
    "SIMPLE_QUESTION_MISSION_ID",
    "build_simple_question_plan",
    "RISK_ASSESSMENT_CAPABILITY",
    "RISK_ASSESSMENT_CAPABILITY_ID",
    "RISK_ASSESSMENT_MISSION_TYPE",
    "RISK_ASSESSMENT_MISSION_ID",
    "build_risk_assessment_plan",
    "ISO_CONTROLS_CAPABILITY",
    "ISO_CONTROLS_CAPABILITY_ID",
    "ISO_CONTROLS_MISSION_TYPE",
    "ISO_CONTROLS_MISSION_ID",
    "build_iso_controls_plan",
    "POLICY_GENERATOR_CAPABILITY",
    "POLICY_GENERATOR_CAPABILITY_ID",
    "POLICY_GENERATOR_MISSION_TYPE",
    "POLICY_GENERATOR_MISSION_ID",
    "build_policy_generator_plan",
    "VENDOR_REVIEW_CAPABILITY",
    "VENDOR_REVIEW_CAPABILITY_ID",
    "VENDOR_REVIEW_MISSION_TYPE",
    "VENDOR_REVIEW_MISSION_ID",
    "build_vendor_review_plan",
    "GAP_ASSESSMENT_CAPABILITY",
    "GAP_ASSESSMENT_CAPABILITY_ID",
    "GAP_ASSESSMENT_MISSION_TYPE",
    "GAP_ASSESSMENT_MISSION_ID",
    "build_gap_assessment_plan",
    "FALLBACK_CAPABILITY_ID",
    "default_capability_catalog",
    "default_mission_catalog",
    "default_intent_recognizer",
    "build_assistant",
]
