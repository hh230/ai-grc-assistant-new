"""Runnable examples — show a `ContextPackage` for the same query under different workflow
policies, so the structural differences (evidence-first vs requirement-first vs two-sided vs
smallest) are visible.

This is a *demonstration* renderer for humans/debugging. The package itself is structured
data (sections → blocks → citations); turning it into prose is a later (LLM) phase's job —
never the builder's.

Run: python -m context_builder.examples
"""

from __future__ import annotations

from pathlib import Path

from context_builder import ContextBuilder, ContextPackage, CorpusParentResolver, WorkflowPolicy
from retrieval_engine import RetrievalEngine, RetrievalQuery
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider

_V2 = Path(__file__).resolve().parents[3]


def render(package: ContextPackage) -> str:
    lines = [
        f"QUERY: {package.query}",
        f"WORKFLOW: {package.workflow}   valid={package.valid}   "
        f"tokens={package.token_count}/{package.budget.max_tokens}",
        f"METRICS: {package.metrics.to_dict()}",
    ]
    for section in package.sections:
        lines.append(f"\n  ┌─ {section.title}  ({section.role.value}, {section.token_count} tok, {len(section.blocks)} blocks)")
        for block in section.blocks:
            tag = "parent" if block.is_parent else f"score={block.score:.3f}"
            lines.append(f"  │   • [{tag}] {block.citation.formatted}")
            snippet = block.text.strip().replace("\n", " ")[:88]
            lines.append(f"  │       {snippet}…")
    return "\n".join(lines)


def main() -> int:
    corpus = InMemoryCorpus.load(_V2 / "knowledge" / "chunks")
    engine = RetrievalEngine(
        InMemoryVectorProvider.load(corpus, _V2 / "knowledge" / "embeddings"),
        InMemoryKeywordProvider(corpus),
    )
    builder = ContextBuilder(parent_resolver=CorpusParentResolver(corpus))

    query = "access control policy"
    ctx = engine.retrieve(RetrievalQuery(text=query, top_k=25))

    for workflow in (WorkflowPolicy.LOOKUP, WorkflowPolicy.GAP_ASSESSMENT,
                     WorkflowPolicy.COMPLIANCE_REVIEW, WorkflowPolicy.COMPARISON):
        pkg = builder.build(ctx, workflow=workflow, budget=4000)
        print("\n" + "=" * 96)
        print(render(pkg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
