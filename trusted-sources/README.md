# Trusted sources (as data)

The curated catalog Autonomous Knowledge Research (Knowledge Intelligence KI-P2, ADR-0026)
plans against — **data, not code** (CLAUDE.md §13's "frameworks are data" principle, the same
one [`/regulatory-sources`](../regulatory-sources/README.md) and
[`/knowledge-catalog`](../knowledge-catalog/README.md) already apply to regulators and
questions). Onboarding a new trusted source is a PR that adds one JSON file here — never a
code change.

Loaded by `grc_knowledge_research_adapters.trusted_source_catalog` into a tuple of
`CatalogedSource`; see that module's docstring for the canonical schema. Layout:
`<jurisdiction>/<source_id>.json`.

**`source_type` must be one of `TrustedSourceType`'s five members**
(`government_regulator`, `official_framework`, `standards_body`, `law_regulation`,
`official_guidance`) — "do not use random blogs" (ADR-0025) is enforced by the loader
rejecting anything else, not by editorial discipline alone.

**`domains` must be a non-empty list of `KnowledgeDomain` values** — the tags the Research
Planner (`grc_knowledge_research.planning.build_research_plan`) matches a question's domain
against to decide this source is worth checking at all.

**Initial set (Saudi Arabia):** the same six regulators already crawled for Regulatory
Intelligence (`/regulatory-sources/sa`) — NCA, SAMA, CMA, SDAIA, MHRSD, ZATCA — reused here
with their already-verified, real URLs, tagged with the knowledge domains their mandate
plausibly covers (e.g. NCA → cybersecurity governance; SDAIA → data protection). See `sa/`.

**Deliberately narrow for now.** Several `KnowledgeDomain`s (contracts, vendor management,
internal controls, audit, policies & procedures) have no cataloged source yet: this catalog
does not invent international standards-body URLs (ISO, NIST, ...) that haven't been
independently verified. A question in an uncataloged domain simply yields an empty research
plan — reported as insufficient evidence, never guessed at from an unverified source. Growing
coverage into these domains is ongoing editorial work (add a reviewed JSON file), not a
code change — the same posture ADR-0025 already took for the question catalog itself.
