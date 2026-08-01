"""Rasheed V2 Pipeline Contracts — the single shared contract library for the AI pipeline.

Pure, immutable data models, shared enums, and provider-neutral interfaces. Zero
infrastructure: no PostgreSQL, no pgvector, no numpy, no OpenAI, no filesystem access.
Every engine (decision-engine, retrieval-engine, context-builder, prompt-orchestrator,
ai-orchestrator) depends on this package; this package depends on nothing.
"""

from pipeline_contracts.citations import (
    REQUIRED_LOCATORS,
    ChunkSource,
    Citation,
    CitationSource,
    build_citation,
    citation_is_complete,
    citation_key,
    clause_key,
    format_citation,
    is_citable,
    missing_facets,
    respan,
)
from pipeline_contracts.context import (
    BUDGET_PRESETS,
    BlockRole,
    BuildMetrics,
    ContextBlock,
    ContextPackage,
    ContextSection,
    OrderingPolicy,
    TokenBudget,
    WorkflowPolicy,
    role_for_profile,
)
from pipeline_contracts.decision import DecisionPlan, Intent, UserRequest
from pipeline_contracts.generation import (
    AuthenticationError,
    GenerationError,
    GenerationProvider,
    InvalidRequest,
    ProviderUnavailable,
    RateLimitError,
    TimeoutError,
)
from pipeline_contracts.intent_registry import (
    INTENT_REGISTRY,
    ORDERING_POLICIES,
    IntentSpec,
    OutputProfile,
    RoutingPolicy,
    spec_for,
)
from pipeline_contracts.llm import (
    Answer,
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
from pipeline_contracts.retrieval import (
    DEFAULT_TOP_K,
    CorpusChunk,
    Filter,
    FusedHit,
    KeywordSearchProvider,
    RetrievalFilter,
    RetrievalQuery,
    RetrievedChunk,
    RetrievedContext,
    ScoredHit,
    VectorSearchProvider,
)
from pipeline_contracts.serialization import dataclass_dict, to_plain
from pipeline_contracts.tenancy import (
    KnowledgeScope,
    RetrievalScope,
    TenancyError,
    TenantContext,
)

__all__ = [
    # decision
    "UserRequest",
    "Intent",
    "DecisionPlan",
    # retrieval
    "Filter",
    "RetrievalFilter",
    "CorpusChunk",
    "ScoredHit",
    "FusedHit",
    "RetrievedChunk",
    "RetrievedContext",
    "RetrievalQuery",
    "DEFAULT_TOP_K",
    "VectorSearchProvider",
    "KeywordSearchProvider",
    # citations (the canonical citation contract + its formatting, validity, identity rules)
    "Citation",
    "CitationSource",
    "ChunkSource",
    "REQUIRED_LOCATORS",
    "is_citable",
    "format_citation",
    "build_citation",
    "citation_is_complete",
    "missing_facets",
    "citation_key",
    "clause_key",
    "respan",
    # context
    "WorkflowPolicy",
    "BlockRole",
    "role_for_profile",
    "ContextBlock",
    "ContextSection",
    "OrderingPolicy",
    "TokenBudget",
    "BUDGET_PRESETS",
    "BuildMetrics",
    "ContextPackage",
    # intent registry
    "INTENT_REGISTRY",
    "ORDERING_POLICIES",
    "IntentSpec",
    "OutputProfile",
    "RoutingPolicy",
    "spec_for",
    # serialization
    "dataclass_dict",
    "to_plain",
    # tenancy (ADR 0040)
    "TenantContext",
    "RetrievalScope",
    "KnowledgeScope",
    "TenancyError",
    # llm
    "Language",
    "SegmentRole",
    "SegmentKind",
    "PromptFamily",
    "PromptSegment",
    "ResponseContract",
    "PromptMetrics",
    "LLMMessage",
    "LLMRequest",
    "Answer",
    # generation port + domain errors
    "GenerationProvider",
    "GenerationError",
    "AuthenticationError",
    "InvalidRequest",
    "RateLimitError",
    "TimeoutError",
    "ProviderUnavailable",
]
