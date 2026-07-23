"""`SearchTool` — a real, read-only GRC search tool that **wraps the frozen `RetrievalEngine`**.

It re-implements nothing: it maps the step `instruction` to a **tenant-scoped** `RetrievalQuery`,
calls `RetrievalEngine.retrieve` (vector ∥ keyword → RRF fusion → ranking → citation gate →
assembly, all in the frozen engine), and maps the `RetrievedContext` to a `ToolStepResult`.

Tenant isolation is the load-bearing part (CLAUDE.md §20, ADR 0040): the query's `Filter.scope` is
`RetrievalScope.for_tenant(tenant.tenant_id)`, so the engine returns this tenant's data ∪ shared
global knowledge and **never another tenant's**. The engine's own defence-in-depth re-checks every
candidate and raises `TenancyError`; the tool turns that into a fail-safe `ok=False`, never a leak.

One tool class backs all three registered tools (`local_search`, `vector_search`, `hybrid_search`):
they differ only in which providers the wrapped engine was built with (see `tools.py`).
"""

from __future__ import annotations

from pipeline_contracts import (
    DEFAULT_TOP_K,
    Filter,
    RetrievalQuery,
    RetrievalScope,
    RetrievedContext,
    TenancyError,
    TenantContext,
    format_citation,
)
from retrieval_engine import RetrievalEngine
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, ToolSpec, ToolStepResult


class SearchTool:
    """A registered `Tool` that searches the knowledge base through a wrapped `RetrievalEngine`."""

    def __init__(
        self,
        engine: RetrievalEngine,
        *,
        name: str,
        description: str,
        top_k: int = DEFAULT_TOP_K,
        version: int = 1,
        snippet_chars: int = 240,
    ) -> None:
        self._engine = engine
        self._top_k = max(1, top_k)
        self._snippet_chars = snippet_chars
        self._spec = ToolSpec(
            name=name, version=version, description=description,
            side_effect=SideEffectProfile.READ_ONLY,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        query_text = str(payload.get(PAYLOAD_INSTRUCTION, "")).strip()
        if not query_text:
            return _fail("no search query given")
        # Tenant boundary (ADR 0040): scope the query to this tenant; the engine returns this
        # tenant's data ∪ global knowledge, never another tenant's.
        query = RetrievalQuery(
            text=query_text,
            filter=Filter(scope=RetrievalScope.for_tenant(tenant.tenant_id)),
            top_k=self._top_k,
        )
        try:
            context = self._engine.retrieve(query)
        except TenancyError as exc:
            return _fail(f"search refused for tenant isolation: {exc}")
        return self._to_result(context).as_payload()

    def _to_result(self, context: RetrievedContext) -> ToolStepResult:
        if not context.results:
            return ToolStepResult(
                ok=True,
                output=f"No results for {context.query!r}.",
                warnings=tuple(context.warnings),
            )
        lines = [f"{len(context.results)} result(s) for {context.query!r}:"]
        for i, r in enumerate(context.results, start=1):
            snippet = " ".join(r.text.split())[: self._snippet_chars]
            lines.append(f"[{i}] {format_citation(r.citation)} — {snippet}")
        return ToolStepResult(
            ok=True,
            output="\n".join(lines),
            source_ids=tuple(r.chunk_id for r in context.results),
            confidence=context.overall_confidence,
            warnings=tuple(context.warnings),
        )


def _fail(reason: str) -> dict[str, object]:
    return ToolStepResult(ok=False, output="", warnings=(reason,)).as_payload()
