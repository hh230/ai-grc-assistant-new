"""The Context Builder — orchestration.

Pipeline (each stage is a small, independently tested module):

    RetrievedContext
      → normalize        (RetrievedChunk → ContextBlock, carry citations through)
      → deduplicate      (chunk_id · checksum · similarity)
      → merge adjacent   (same doc + heading + clause, consecutive)
      → expand parents   (add the child's heading section, when useful, via a resolver port)
      → order + section  (workflow-aware: evidence-first / requirement-first / two-sided / …)
      → enforce budget   (token budget, whole blocks, complete sections)
      → validate         (reject over-budget / lost-citation / duplicate / empty-section)
    → ContextPackage (+ BuildMetrics)

No prompting, no LLM, no answers, no RAG — this is context *preparation* only.
"""

from __future__ import annotations

from context_builder import deduplicate as dedup
from context_builder import ordering
from context_builder.budget import HeuristicTokenCounter, TokenCounter, assign_token_counts, enforce_budget
from context_builder.builder import blocks_from_context
from context_builder.expansion import DEFAULT_MAX_EXPANSIONS, ParentResolver, expand_parents
from context_builder.merge import merge_adjacent
from context_builder.models import BuildMetrics, ContextPackage, TokenBudget, WorkflowPolicy
from context_builder.validator import validate
from pipeline_contracts.retrieval import RetrievedContext

DEFAULT_BUDGET_TOKENS = 8000


class ContextBuilder:
    """Stateless builder. Inject a `TokenCounter` (default heuristic) and, to enable parent
    expansion, a `ParentResolver` (e.g. `CorpusParentResolver`). With no resolver, expansion
    is a no-op and every other stage still runs."""

    def __init__(
        self,
        *,
        token_counter: TokenCounter | None = None,
        parent_resolver: ParentResolver | None = None,
        sim_threshold: float = dedup.DEFAULT_SIMILARITY_THRESHOLD,
        max_expansions: int = DEFAULT_MAX_EXPANSIONS,
    ) -> None:
        self._counter = token_counter or HeuristicTokenCounter()
        self._resolver = parent_resolver
        self._sim_threshold = sim_threshold
        self._max_expansions = max_expansions

    def build(
        self,
        context: RetrievedContext,
        *,
        workflow: WorkflowPolicy | str = WorkflowPolicy.GENERAL,
        budget: int | TokenBudget = DEFAULT_BUDGET_TOKENS,
        attachment_document_ids: tuple[str, ...] = (),
    ) -> ContextPackage:
        policy = workflow if isinstance(workflow, WorkflowPolicy) else WorkflowPolicy.from_intent(workflow)
        token_budget = budget if isinstance(budget, TokenBudget) else TokenBudget(max_tokens=int(budget))
        metrics = BuildMetrics()

        # 1. normalize
        blocks = blocks_from_context(context)
        metrics.chunks_in = len(blocks)

        # 2. deduplicate
        blocks, duplicates = dedup.deduplicate(blocks, sim_threshold=self._sim_threshold)
        metrics.duplicates_removed = duplicates

        # 3. merge adjacent (stitch same-clause fragments before adding parents)
        blocks, merged = merge_adjacent(blocks)
        metrics.merged_chunks = merged

        # 4. parent expansion (no-op without a resolver)
        blocks, expansions = expand_parents(blocks, self._resolver, max_expansions=self._max_expansions)
        metrics.parent_expansions = expansions

        # 4b. final exact-text guard — merge/expansion can reintroduce byte-identical text
        # (a restated clause, or two section intros that share boilerplate). Hash-only, so it
        # never drops a distinct child.
        blocks, extra_dupes = dedup.dedup_by_content_hash(blocks)
        metrics.duplicates_removed += extra_dupes

        # 5. token counts for every surviving/merged/expanded block
        assign_token_counts(blocks, self._counter)

        # 6. order into workflow-appropriate sections
        sections = ordering.order_into_sections(
            blocks, policy, attachment_document_ids=attachment_document_ids
        )

        # 7. enforce the token budget (balanced fill for two-sided comparison)
        balanced = ordering.policy_for(policy).balanced
        sections, trimmed = enforce_budget(sections, token_budget, balanced=balanced)
        metrics.blocks_trimmed = trimmed

        # metrics roll-up
        metrics.sections = len(sections)
        metrics.chunks_selected = sum(len(s.blocks) for s in sections)
        metrics.chunks_removed = metrics.duplicates_removed + merged + trimmed
        metrics.token_usage = token_budget.used_tokens
        metrics.remaining_budget = token_budget.remaining

        warnings = list(context.warnings)
        package = ContextPackage(
            query=context.query,
            workflow=policy.value,
            budget=token_budget,
            sections=sections,
            metrics=metrics,
            warnings=warnings,
        )

        # 8. validate; a failed package is returned with valid=False and the reasons, never
        #    silently — the caller decides whether to proceed.
        result = validate(package)
        package.valid = result.is_valid
        if not result.is_valid:
            package.warnings.extend(f"validation: {issue}" for issue in result.issues)
        return package
