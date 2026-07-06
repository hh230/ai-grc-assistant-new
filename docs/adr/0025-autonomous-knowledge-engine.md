# ADR 0025: Autonomous Knowledge Engine (KI-P1) — catalog-driven questions, deterministic gap detection, Tool-audited discovery, zero unsourced knowledge

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §1, §5, §9, §11, §12, §13, §15, §19, §20; ADR 0006, 0017, 0018, 0019,
  0020, 0021, 0022, 0024

## Context

Everything built so far in the Policy Intelligence line (Regulatory Intelligence, Policy
Hunter, Policy Analyst, Policy Builder) *consumes* knowledge: confirmed regulatory
obligations, a tenant's own policies. Nothing yet *creates* general GRC/compliance/legal
knowledge — the kind of professional judgment call a compliance officer looks up
independently of any one regulation, e.g. "what clauses should exist in a vendor contract" or
"what controls are required for third-party risk." This ADR (Knowledge Intelligence KI-P1)
starts that layer: an engine that generates the important questions a GRC/compliance/legal
professional needs answered, checks what the knowledge base already knows, and — when
something is missing, stale, or weakly supported — coordinates a grounded, cited discovery
step.

This phase inherits every governing constraint the Policy Intelligence line has already
established and is asked to satisfy them for a fundamentally *harder* problem than obligation
classification or coverage scanning: unlike "does this obligation's text match this policy's
text" (a comparison Policy Hunter can do deterministically), "what should a good vendor
contract contain" has no closed-form deterministic answer — it requires either free-form
generation or a grounded read of an actual authoritative source. CLAUDE.md §1's stance ("trust
is the product... we'd rather say I don't know than guess") and the explicit requirement
"no automatic legal conclusions without source evidence" ruled out an LLM answering from its
own training knowledge. The design question this phase had to resolve was therefore not
"deterministic or LLM" (as it was for Policy Hunter/Analyst) but "how do we let an LLM
synthesize an answer without ever letting it invent one."

## Decision

We will, mapping directly onto the seven architecture requirements asked for:

**1. Knowledge Question Generator — catalog-driven, not model-invented.** `/knowledge-catalog/
<domain>.json` holds 33 curated questions across the 11 named domains (Governance, Risk
Management, Compliance, Internal Controls, Audit, Contracts, Vendor Management, Data
Protection, Cybersecurity Governance, Policies & Procedures, Regulatory Obligations) — **data,
not code**, loaded by `grc_knowledge_intelligence.question_catalog.build_catalog` (the same
"frameworks are data" pattern, CLAUDE.md §13, `grc_regulatory_intelligence.source_config`
already established for regulators). An LLM does not invent the questions a knowledge base
answers: CLAUDE.md §1 prefers a reviewed, auditable set over free-form generation for the same
reason it prefers a reviewed set of trusted sources over an open crawl.

**2. Knowledge Gap Detector — pure, deterministic, no LLM.**
`grc_knowledge_intelligence.gap_detection.detect_gaps` classifies every catalog question
against the knowledge base's current item (at most one per `question_id`) as `MISSING`
(never researched), `OUTDATED` (explicitly flagged `outdated`/`needs_review`, or simply stale
by age — default 365 days), `WEAK_CONFIDENCE` (answered, but under the confidence bar —
default 0.7), or `ANSWERED`. The same reasoning ADR-0020/0021 used for Policy Hunter/Analyst
applies again: this is a comparison problem, not a generation problem, so it gets a
reproducible algorithm.

**3. Research Agent — Tool-audited LLM synthesis, grounded in one already-fetched excerpt,
never a live crawl in this phase.** `grc_knowledge_intelligence_adapters
.SynthesizeKnowledgeAnswerTool` calls the provider-agnostic `ChatModel` through the Tool
Registry (`ToolSideEffect.READ_ONLY`, permission-checked
`Permission("knowledge_intelligence")`) — authorized, validated, and unconditionally audited
exactly like `ClassifyRegulatoryObligationTool` already is (ADR-0018). The prompt instructs
the model to answer **using only the given excerpt**, never outside knowledge, and to return
confidence `0` rather than guess when the excerpt does not address the question — the adapter
translates a `0` confidence into `KnowledgeExtractionError`, so "could not ground an answer
here" is a first-class outcome, not a bug. **What this phase does not do**: fetch that excerpt
itself. `SourceExcerpt` (already-fetched text with `TrustedSource` provenance) is an input the
caller provides — exactly the same split ADR-0018 made for Regulatory Intelligence (pure
engine, no crawling) versus ADR-0019 (crawling, a later phase). A real trusted-source fetch
step is explicit future work, reusing `grc_regulatory_crawlers`' already-built, polite,
robots.txt-respecting HTTP fetcher rather than building a second one.

**4. Knowledge Extraction — a validated `KnowledgeItem`, never raw LLM prose.** The LLM's JSON
is validated strictly (`_RawSynthesisPayload`): an empty `answer`/`applicable_context` or a
`confidence` outside `[0, 1]` is rejected (`KnowledgeSynthesisRejectedError`) before it can
ever become a candidate item. `KnowledgeItem` (`grc_knowledge_intelligence.models`) carries
every field named in the requirement — `question`, `answer`, `domain`, `category`,
`applicable_context`, `source`, `citation`, `jurisdiction`, `confidence`, `status`
(`VerificationStatus`), `last_verified`, `version` — and its `source_type` is one of exactly
five `TrustedSourceType` members (government regulator, official framework, standards body,
law/regulation, official guidance): **there is no way to construct a `TrustedSource` backed by
an unclassified site.** "Do not use random blogs" is enforced by the type system, not a
docstring.

**5. Storage — one new platform-scope table, the established pattern.**
`apps/web/lib/db/migrations/0018_knowledge_items.sql` adds `knowledge_items`, platform-scope
(no `tenant_id`) like `regulatory_obligations` — GRC knowledge is shared reference data every
tenant draws from. `grc_persistence_web.KnowledgeItemRepository` upserts on
`version_hash` (`grc_knowledge_intelligence.compute_version_hash`, a content-derived
fingerprint of the question + excerpt): an unchanged re-discovery is a no-op that **never
resets an already-verified item's status** — the one behavior this phase had to get exactly
right, since a naive upsert-and-reset-to-discovered would silently undo a human's prior
verification every time discovery re-ran. A genuinely changed answer bumps `version` and
resets to `discovered`, correctly asking a human to look again. Reusable, in principle, by
Policy Hunter, Policy Analyst, Policy Builder, and a future Contract Reviewer — **none of
which are wired to read from it in this phase** (see Consequences).

**6. Verification — four states, human-only transitions, not a Tool.**
`VerificationStatus` (`discovered` → `verified`/`needs_review`/`outdated`) mirrors
`ClassificationStatus`'s never-auto-confirm posture (ADR-0018) with one more state
(`needs_review`, since a professional's judgment call is more often "close, but needs a
tweak" than binary confirmed/rejected). `KnowledgeItemRepository.set_verification_status` is a
plain repository method, not a Tool: marking something verified is a human record-keeping
decision, not an AI capability the Tool Registry needs to mediate — the same reasoning that
keeps policy `submit-for-review`/`approve`/`publish` as `grc_services` commands rather than
Tools.

**7. Refresh Engine — the gap detector's `OUTDATED` classification *is* the refresh logic;
scheduling is explicit future work.** "Which knowledge items are due for a fresh look" is
already answered by `detect_gaps`'s age/status checks — there is no separate "refresh" engine
to build, only a scheduler to eventually point at it. Per ADR-0019's own precedent ("any
scheduling — apps/worker/cron wiring — rejected per explicit scope"), no `apps/worker` job is
wired in this phase.

## Consequences

**Positive**
- Every `KnowledgeItem` traces to exactly one classified, trusted source with a citation —
  there is no field or code path for unsourced knowledge, satisfying "no automatic legal
  conclusions without source evidence" by construction, not by convention.
- The idempotent-upsert-preserves-verification behavior is the single most important
  correctness property this phase introduces, and it is directly tested (`test_knowledge.py`):
  re-running discovery over unchanged source text can never silently revert a human's
  verification decision.
- Zero new architectural patterns: catalog-as-data mirrors the Framework Engine and
  `regulatory-sources`; the pure-engine/Tool-adapter package split mirrors
  `grc_regulatory_intelligence`/`-adapters` exactly; the Tool itself mirrors
  `ClassifyRegulatoryObligationTool` line for line where the shapes coincide.
- 40 new tests (13 pure engine, 9 Tool-audited adapter, 6 persistence, plus catalog-loading
  checks) — all deterministic except the two adapter tests that exercise a fake, deterministic
  `ChatModel`; nothing requires network or an API key to pass.

**Negative / costs**
- **No live trusted-source fetching.** This is the largest gap: the engine can synthesize an
  answer from a `SourceExcerpt`, but nothing yet discovers and fetches one from a real
  regulator site, standards body, or framework publication. A human (or a future adapter)
  must supply the excerpt today. This is the same shape of gap ADR-0018 accepted for
  Regulatory Intelligence before ADR-0019 closed it, and the intended path is identical: reuse
  `grc_regulatory_crawlers`, not build a second crawler.
- **No consumer wiring.** Policy Hunter, Policy Analyst, and Policy Builder do not read from
  `knowledge_items` yet — "knowledge must be reusable by" is a storage-shape promise (the
  schema and repository exist and are stable), not a consumer integration delivered in this
  phase.
- **No `apps/api` HTTP endpoint, no scheduled refresh, no UI.** Explicitly out of scope, at the
  same boundary every prior Policy Intelligence phase held itself to before its own dedicated
  exposure phase (PI-P5/PI-P6 for Hunter/Analyst).
- **The question catalog is small and hand-curated (33 questions).** Deliberately: CLAUDE.md
  §1 prefers a reviewed set that will grow by PR over one an LLM invents at request time.
  Growing coverage is ongoing editorial work, not a code change.

## Alternatives considered

- **Let the LLM answer from its own general knowledge (no excerpt required).** Rejected
  outright: this is exactly "automatic legal conclusions without source evidence," which the
  requirement explicitly forbids. Every synthesis call requires a `SourceExcerpt`; there is no
  code path that calls the model without one.
- **Generate the question catalog with an LLM instead of curating it as data.** Rejected for
  the same reason ADR-0013/CLAUDE.md §13 treat frameworks as data: the *questions* a knowledge
  base promises to answer are a curation decision as important as the answers, and a fixed,
  reviewable file is auditable in a way a runtime-generated list is not.
- **Build a new trusted-source crawler for this phase instead of deferring to a future reuse
  of `grc_regulatory_crawlers`.** Rejected: a second, independently-built HTTP fetcher for the
  same class of problem (polite, robots.txt-respecting requests to a fixed set of trusted
  domains) would duplicate work `grc_regulatory_crawlers` already does well, and would
  guarantee subtly different fetch behavior between the two subsystems for no benefit.
- **Skip the confidence-0 "not grounded" signal and instead throw for any low-confidence
  answer.** Rejected: a low-but-nonzero confidence is useful information (a `WEAK_CONFIDENCE`
  gap, not a failure) and should still produce a storable item for a human to judge; only a
  genuinely irrelevant excerpt (confidence exactly 0, the model's own signal that the excerpt
  doesn't address the question at all) should be treated as "no answer."
- **Give `KnowledgeItemRepository.upsert` a full version-history table instead of one row per
  question.** Rejected for this phase's scope: nothing yet needs to browse prior answers to a
  question, only "what do we currently believe, and how much do we trust it." A history table
  is a straightforward additive migration later if a consumer needs it.
