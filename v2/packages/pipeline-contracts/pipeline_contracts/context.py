"""Context contracts — the structured, citation-preserving shape of assembled context.

The context stage turns a `RetrievedContext` into a **structured `ContextPackage`** —
never one big string. The shape is deliberately layered so a later LLM phase can format it
however it likes without losing provenance:

    ContextPackage
      ├─ ContextSection (workflow-ordered: Requirements / Evidence / Policies / …)
      │    └─ ContextBlock  (one coherent unit of context)
      │         └─ Citation (document · page · heading · clause · code · profile)
      └─ BuildMetrics + TokenBudget + warnings

Citations are the retrieval contract's own `Citation` objects, carried through untouched —
so "no citation may be lost" is guaranteed by construction, not by copying fields around.

These are contracts only: the build pipeline (dedup, merge, expansion, ordering,
budgeting, validation) lives in the context-builder package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pipeline_contracts.citations import Citation
from pipeline_contracts.serialization import dataclass_dict


class WorkflowPolicy(str, Enum):
    """Which context strategy to apply. Values match the Decision Engine's `Intent` strings
    so a `DecisionPlan.intent` selects a policy directly (`WorkflowPolicy(plan.intent)`),
    with `GENERAL` as the balanced fallback for anything unmapped."""

    LOOKUP = "lookup"
    EXPLANATION = "explanation"
    COMPARISON = "comparison"
    COMPLIANCE_REVIEW = "compliance_review"
    POLICY_REVIEW = "policy_review"
    GAP_ASSESSMENT = "gap_assessment"
    DOCUMENT_ANALYSIS = "document_analysis"
    GENERAL = "general"

    @classmethod
    def from_intent(cls, intent: str | Enum | None) -> WorkflowPolicy:
        value = intent.value if isinstance(intent, Enum) else str(intent)
        try:
            return cls(value)
        except ValueError:
            return cls.GENERAL


class BlockRole(str, Enum):
    """The GRC role a block plays, derived from its document profile. Ordering strategies
    sort *sections* by role (requirement-first, evidence-first, …)."""

    REQUIREMENT = "requirement"  # normative external sources: law, regulation, iso, control framework
    POLICY = "policy"            # the organisation's own corporate policies
    EVIDENCE = "evidence"        # operational artefacts: contracts, spreadsheets, other docs
    GENERAL = "general"          # anything unclassified

    @property
    def title(self) -> str:
        return {
            BlockRole.REQUIREMENT: "Requirements & Regulations",
            BlockRole.POLICY: "Policies",
            BlockRole.EVIDENCE: "Evidence & Supporting Documents",
            BlockRole.GENERAL: "Additional Context",
        }[self]


# document_profile → role. Profiles come from the Chunking Engine's catalog.
_PROFILE_ROLE: dict[str, BlockRole] = {
    "law": BlockRole.REQUIREMENT,
    "regulation": BlockRole.REQUIREMENT,
    "iso_standard": BlockRole.REQUIREMENT,
    "control_framework": BlockRole.REQUIREMENT,
    "corporate_policy": BlockRole.POLICY,
    "contract": BlockRole.EVIDENCE,
    "spreadsheet": BlockRole.EVIDENCE,
    "unmapped": BlockRole.GENERAL,
}


def role_for_profile(document_profile: str | None) -> BlockRole:
    return _PROFILE_ROLE.get(document_profile or "", BlockRole.GENERAL)


@dataclass(frozen=True)
class OrderingPolicy:
    """How a workflow arranges context: which roles lead, whether sections split per
    document (comparison), collapse to one (lookup / document analysis), cap blocks, or
    fill the budget evenly. Pure data — the ordering *algorithm* lives in the context
    builder; the per-intent policy instances live in the intent registry."""

    role_order: tuple[BlockRole, ...]
    split_by_document: bool = False   # comparison: one section per side
    attachment_only: bool = False     # document analysis: attachment blocks only
    single_section: bool = False      # lookup / document analysis: collapse to one section
    single_title: str = "Context"
    max_blocks: int | None = None     # hard cap on total blocks (lookup keeps it smallest)
    balanced: bool = False            # comparison: split the budget evenly across sections


@dataclass
class ContextBlock:
    """One coherent unit of context: text plus its complete citation and provenance. A
    block is either a single retrieved chunk, an adjacent-merge of several, or an expanded
    parent heading. It is mutable during the build pipeline (merge/expansion rewrite it),
    then frozen in practice once the package is emitted."""

    block_id: str
    document_id: str
    role: BlockRole
    text: str
    citation: Citation
    heading_path: tuple[str, ...]
    page_start: int | None
    page_end: int | None
    code: str | None
    document_profile: str | None
    score: float
    confidence: float
    token_count: int = 0
    is_parent: bool = False
    source_chunk_ids: tuple[str, ...] = ()
    content_hash: str = ""

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self, exclude=("content_hash",))


@dataclass
class ContextSection:
    """A titled group of blocks sharing a role/side. Sections are what workflow ordering
    arranges (evidence-first, requirement-first, policy-then-regulation, …)."""

    title: str
    role: BlockRole
    blocks: list[ContextBlock] = field(default_factory=list)

    @property
    def token_count(self) -> int:
        return sum(b.token_count for b in self.blocks)

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self, extra={"token_count": self.token_count})


# The five supported budget presets (in tokens), plus a helper to snap/validate.
BUDGET_PRESETS: tuple[int, ...] = (2000, 4000, 8000, 16000, 32000)


@dataclass
class TokenBudget:
    """A configurable token budget. `max_tokens` is the ceiling; `used_tokens` is filled in
    as blocks are admitted. Presets: 2k / 4k / 8k / 16k / 32k."""

    max_tokens: int
    used_tokens: int = 0

    @property
    def remaining(self) -> int:
        return self.max_tokens - self.used_tokens

    def fits(self, tokens: int) -> bool:
        return self.used_tokens + tokens <= self.max_tokens

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self, extra={"remaining": self.remaining})


@dataclass
class BuildMetrics:
    """Statistics for one build — the observability contract of the context stage."""

    chunks_in: int = 0
    chunks_selected: int = 0
    chunks_removed: int = 0
    duplicates_removed: int = 0
    parent_expansions: int = 0
    merged_chunks: int = 0
    blocks_trimmed: int = 0
    sections: int = 0
    token_usage: int = 0
    remaining_budget: int = 0

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass
class ContextPackage:
    """The context stage's output: a structured, ordered, budgeted, cited context bundle,
    ready for a future LLM phase to format. Never a single string."""

    query: str
    workflow: str
    budget: TokenBudget
    sections: list[ContextSection] = field(default_factory=list)
    metrics: BuildMetrics = field(default_factory=BuildMetrics)
    warnings: list[str] = field(default_factory=list)
    valid: bool = True

    def all_blocks(self) -> list[ContextBlock]:
        return [b for s in self.sections for b in s.blocks]

    def all_citations(self) -> list[Citation]:
        return [b.citation for b in self.all_blocks()]

    @property
    def token_count(self) -> int:
        return sum(s.token_count for s in self.sections)

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)
