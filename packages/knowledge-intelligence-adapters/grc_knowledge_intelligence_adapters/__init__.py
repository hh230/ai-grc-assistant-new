"""grc_knowledge_intelligence_adapters — the Autonomous Knowledge Engine's concrete,
Tool-audited LLM synthesis adapter (KI-P1, ADR-0025). Implements
``grc_knowledge_intelligence.KnowledgeExtractorPort``; never imported back by the pure engine.
"""

from __future__ import annotations

from .exceptions import KnowledgeSynthesisRejectedError
from .synthesis import (
    TOOL_NAME,
    TOOL_VERSION,
    LlmKnowledgeExtractor,
    SynthesizeKnowledgeAnswerInput,
    SynthesizeKnowledgeAnswerOutput,
    SynthesizeKnowledgeAnswerTool,
)

__all__ = [
    "TOOL_NAME",
    "TOOL_VERSION",
    "KnowledgeSynthesisRejectedError",
    "LlmKnowledgeExtractor",
    "SynthesizeKnowledgeAnswerInput",
    "SynthesizeKnowledgeAnswerOutput",
    "SynthesizeKnowledgeAnswerTool",
]
