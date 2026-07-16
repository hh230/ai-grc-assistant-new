"""Rasheed V2 AI Orchestrator — the composition root and single entry point of the AI
pipeline. Coordinates DecisionEngine → RetrievalEngine → ContextBuilder →
PromptOrchestrator → GenerationProvider; owns nothing else."""

# Backward-compatible re-exports: the port now lives in pipeline-contracts, the OpenAI
# adapter in generation-engine (Phase 12). Old import paths keep working; new code should
# import from the owning packages.
from generation_engine import OpenAIGenerationProvider
from pipeline_contracts import GenerationProvider

from ai_orchestrator.models import (
    ApprovalRequest,
    CancellationToken,
    PipelineCancelled,
    PipelineHooks,
    PipelineMetrics,
    PipelineResult,
    PipelineStage,
    PipelineStageError,
    PipelineStatus,
)
from ai_orchestrator.orchestrator import AIOrchestrator

__all__ = [
    "AIOrchestrator",
    "GenerationProvider",
    "OpenAIGenerationProvider",
    "PipelineHooks",
    "PipelineMetrics",
    "PipelineResult",
    "PipelineStage",
    "PipelineStatus",
    "PipelineStageError",
    "PipelineCancelled",
    "CancellationToken",
    "ApprovalRequest",
]
