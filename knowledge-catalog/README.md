# Knowledge catalog (as data)

The important questions a GRC/compliance/legal professional needs answers for, across
domains, live here as **data, not code** (CLAUDE.md §13's "frameworks are data" principle,
applied to knowledge questions — see
[ADR-0025](../docs/adr/0025-autonomous-knowledge-engine.md)). Adding a new question to a
domain is a PR that edits one JSON file here — never a code change to the Knowledge Question
Generator itself.

Loaded by `grc_knowledge_intelligence.question_catalog` into a tuple of `KnowledgeQuestion`
value objects; see that module's docstring for the canonical schema. Layout:
`<domain>.json`, one file per `KnowledgeDomain` member.

**Why data, not an LLM generating arbitrary questions:** CLAUDE.md §1 prefers a reproducible,
curated set of questions a domain expert has actually vetted over a model inventing new ones
at random — the *questions* a knowledge base should answer are exactly as important to get
right as the answers, and a fixed, reviewable catalog is auditable in a way free-form
generation is not. Extending coverage is a deliberate, reviewed addition, not a runtime
decision.

**Initial set (11 domains, 33 questions):** Governance, Risk Management, Compliance, Internal
Controls, Audit, Contracts, Vendor Management, Data Protection, Cybersecurity Governance,
Policies & Procedures, Regulatory Obligations — three questions each, covering the areas
named in ADR-0025.

Each question's `question_id` is a stable identifier (`<domain>.<slug>`) that
`KnowledgeItem`s reference — renaming a `question_id` here orphans any existing knowledge
items answering it, so treat it as an append-only key, not free text to edit.
