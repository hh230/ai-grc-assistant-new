"""The Prompt Orchestrator's data model.

The shapes themselves (`LLMRequest`, `PromptSegment`, `ResponseContract`, `PromptMetrics`,
and the `Language` / `SegmentRole` / `SegmentKind` / `PromptFamily` enums) are shared
pipeline contracts and live in the `pipeline-contracts` package; this module re-exports
them so every existing `prompt_orchestrator.models` import keeps working.

The orchestrator's whole job is to turn `DecisionPlan + ContextPackage + UserRequest` into a
**provider-agnostic `LLMRequest`** — the complete, structured request that a *later* phase
will hand to some LLM. It is never a single string, and it names no provider.

    LLMRequest
      ├─ PromptSegment[]        ordered layers, each with a role + kind + source (versioned):
      │     System Prompt → Developer Instructions → Workflow Prompt →
      │     Policies → Context → User Request → Response Contract
      ├─ ResponseContract       required sections / citations / formatting / confidence / forbidden
      ├─ PromptMetrics          sizes, tokens, policies applied, language, prompt versions
      └─ params + warnings + valid

`messages()` collapses the layered segments into the conventional system+user shape any
provider can consume, while the segments preserve the full structure for audit and for
providers that support a distinct developer role.
"""

from __future__ import annotations

from pipeline_contracts.llm import (
    Language,
    LLMMessage,
    LLMRequest,
    PromptFamily,
    PromptMetrics,
    PromptSegment,
    ResponseContract,
    SegmentKind,
    SegmentRole,
)

__all__ = [
    "Language",
    "LLMMessage",
    "LLMRequest",
    "PromptFamily",
    "PromptMetrics",
    "PromptSegment",
    "ResponseContract",
    "SegmentKind",
    "SegmentRole",
]
