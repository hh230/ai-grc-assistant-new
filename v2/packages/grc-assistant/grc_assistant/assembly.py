"""The composition that replaces `EchoExecutor` with the **real** Execution Platform (ADR 0046,
Step A of the Execution wiring).

The Execution Platform already exists and is frozen:

    Mission → ExecutionPort → RegistryExecutor → Tool Registry → Tool → Result

`RegistryExecutor` (pipeline-tool) implements the frozen `ExecutionPort` by resolving a step to a
Tool via the frozen `ToolRegistry` and invoking it. All that was missing was **wiring it in**: the
`MissionRuntime` defaults to the reference `EchoExecutor`, so missions echoed instead of running
tools. This module is that wiring — nothing more:

    registry = ToolRegistry(); registry.register(PipelineTool(orchestrator))
    mission_runtime = build_tool_backed_mission_runtime(registry)  # RegistryExecutor, not Echo
    assistant = build_assistant(mission_runtime)                   # every capability now runs tools

It is **composition only**: it adds no domain, no port, no tool, and changes nothing in the Core,
the Mission layer, or the Assistant. Swapping Echo for real tools is a constructor choice — the
payoff of the ports design (the Assistant/Mission Engine never learn which executor backs a step).
"""

from __future__ import annotations

from ai_orchestrator import AIOrchestrator
from context_builder import ContextBuilder
from decision_engine import DecisionEngine
from framework_library import ControlLibraryTool, FrameworkLibrary
from llm_tools import LLMTool
from mission_integration import MissionRuntime
from mission_store.config import TABLE
from mission_store.outbox_schema import OUTBOX_TABLE
from pipeline_contracts import Filter, GenerationProvider, ScoredHit
from pipeline_tool import RUN_PIPELINE_TOOL, PipelineRunner, PipelineTool, RegistryExecutor
from prompt_orchestrator import PromptOrchestrator
from retrieval_engine import RetrievalEngine
from retrieval_engine.providers.interfaces import KeywordSearchProvider
from search_tools import build_local_search_tool
from tool_registry import ToolRegistry


class _NoVectorProvider:
    """A vector provider that contributes nothing — lets the pipeline retrieve on keyword search
    only, which needs no embeddings. Production swaps in a vector provider over pgvector."""

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        return []


def build_grc_orchestrator(
    keyword_provider: KeywordSearchProvider, generation_provider: GenerationProvider
) -> AIOrchestrator:
    """Build the AI Orchestrator whose **retrieval reads the given knowledge base** — so
    `run_pipeline`, and every capability's grounded step, answers over the **customer's own
    ingested data ∪ shared global knowledge**, not the global library alone (product roadmap P1
    integration). The pipeline already scopes retrieval to the run's tenant
    (`RetrievalScope.from_context`), so passing a provider over a tenant-aware store is the whole
    wiring: pass `TenantKnowledgeBase.keyword_provider()`.

    Keyword retrieval only (no embeddings needed in-memory); production adds a vector provider over
    pgvector with **no change above this function**. The rest of the pipeline (decision, context,
    prompt, generation) is the standard composition."""
    return AIOrchestrator(
        decision_engine=DecisionEngine(),
        retrieval_engine=RetrievalEngine(_NoVectorProvider(), keyword_provider),
        context_builder=ContextBuilder(),
        prompt_orchestrator=PromptOrchestrator(),
        generation_provider=generation_provider,
    )


def build_grc_tool_registry(
    orchestrator: PipelineRunner,
    generation_provider: GenerationProvider,
    keyword_provider: KeywordSearchProvider,
) -> ToolRegistry:
    """Assemble the standard GRC tool set into a `ToolRegistry`:

    - **Local Search** (`local_search`) — tenant-scoped lexical search over the given knowledge base
      (`keyword_provider`). The composites' **gather** tool: it retrieves the **customer's own
      ingested data ∪ global knowledge** without the framework-profile routing the pipeline applies,
      so a capability answers over the customer's documents (product roadmap P1 integration).
    - **Framework Library** (`framework_control_library`) — bundled ISO 27001 / CIS / NIST catalogs.
    - **LLM Tool** (`generate_text`) — raw generation; the **synthesis** tool a composite's last
      uses to write its deliverable *from* the prior gather steps' output (ADR 0051).
    - **Pipeline Tool** (`run_pipeline`) — grounded single-shot RAG for Simple Question.

    Capabilities name tools by registry name (CLAUDE.md §10) and the executor resolves them per step
    (ADR 0048). Adding a real tool is registering it here — no Assistant or Core change."""
    registry = ToolRegistry()
    registry.register(build_local_search_tool(keyword_provider))
    registry.register(ControlLibraryTool(FrameworkLibrary.from_bundled()))
    registry.register(LLMTool(generation_provider))
    registry.register(PipelineTool(orchestrator))
    return registry


def build_tool_backed_mission_runtime(
    registry: ToolRegistry,
    *,
    tool_name: str = RUN_PIPELINE_TOOL,
    dsn: str | None = None,
    missions_table: str = TABLE,
    outbox_table: str = OUTBOX_TABLE,
) -> MissionRuntime:
    """A `MissionRuntime` whose `ExecutionPort` is the real `RegistryExecutor`, not the reference
    `EchoExecutor` — so mission steps run **real tools** resolved from the
    given `ToolRegistry`. `tool_name` selects which registered tool the executor routes steps to
    (default: the Pipeline Tool). Everything else is a normal `MissionRuntime`; the Assistant built
    over it (`assistant_runtime.build_assistant`) is unchanged."""
    return MissionRuntime(
        executor=RegistryExecutor(registry, tool_name=tool_name),
        dsn=dsn,
        missions_table=missions_table,
        outbox_table=outbox_table,
    )
