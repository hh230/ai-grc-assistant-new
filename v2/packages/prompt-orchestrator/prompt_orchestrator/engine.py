"""Segment assembly — build the ordered list of `PromptSegment`s that make up an LLMRequest.

This is the mechanical layer: given the already-rendered text for each layer (system,
developer, workflow, policies, context, user, contract) and the versioned source id of each,
it produces the seven segments in canonical order with per-segment token estimates. The
*selection* of what goes in each layer is the orchestrator's job; this module just assembles.

Token estimation reuses the Context Builder's estimator, so token accounting is consistent
across the two phases.
"""

from __future__ import annotations

from dataclasses import dataclass

from context_builder.budget import estimate_tokens

from prompt_orchestrator.models import PromptSegment, SegmentKind, SegmentRole

# canonical layer order + the role each maps to
_LAYER_ORDER: tuple[tuple[SegmentKind, SegmentRole, str], ...] = (
    (SegmentKind.IDENTITY, SegmentRole.SYSTEM, "System Prompt"),
    (SegmentKind.DEVELOPER_INSTRUCTIONS, SegmentRole.DEVELOPER, "Developer Instructions"),
    (SegmentKind.WORKFLOW, SegmentRole.DEVELOPER, "Workflow Prompt"),
    (SegmentKind.POLICIES, SegmentRole.DEVELOPER, "Policies"),
    (SegmentKind.CONTEXT, SegmentRole.USER, "Context"),
    (SegmentKind.USER_REQUEST, SegmentRole.USER, "User Request"),
    (SegmentKind.RESPONSE_CONTRACT, SegmentRole.DEVELOPER, "Expected Response Contract"),
)


@dataclass(frozen=True)
class LayerContent:
    content: str
    source: str = ""


def assemble(layers: dict[SegmentKind, LayerContent]) -> list[PromptSegment]:
    """Assemble segments in canonical order. A layer absent from `layers` (or with empty
    content) is skipped — e.g. no Policies for a bare conversation."""
    segments: list[PromptSegment] = []
    for kind, role, title in _LAYER_ORDER:
        layer = layers.get(kind)
        if layer is None or not layer.content:
            continue
        segments.append(
            PromptSegment(
                role=role,
                kind=kind,
                title=title,
                content=layer.content,
                source=layer.source,
                estimated_tokens=estimate_tokens(layer.content),
            )
        )
    return segments
