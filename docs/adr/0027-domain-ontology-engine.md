# ADR 0027: Domain Ontology Engine (KI-P3) — a structured GRC/Compliance/Governance/Risk/Legal/Contracts taxonomy, template-based question generation, and illustrative cross-cutting relationships

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §1, §5, §13, §15, §16, §20; ADR 0025, 0026

## Context

KI-P1 (ADR-0025) gave the Knowledge Engine a small, hand-curated question catalog (33
questions across 11 domains) and KI-P2 (ADR-0026) gave it the ability to research an answer
for one of those questions from a curated trusted-source catalog. Both are correct but narrow:
the catalog only asks what a human happened to write down, and neither phase gives the system
any structured notion of *what exists* within a domain — what topics Governance actually
covers, what a vendor contract is expected to contain, or how a requirement relates to a
control. This phase (Knowledge Intelligence KI-P3) is explicitly not a new agent and not a new
capability to *act*; it is a knowledge-representation phase that teaches the system the shape
of the professional domains it operates in, so future phases (a richer question catalog, a
Contract Reviewer, a real knowledge graph) have real structure to build on instead of a flat
list of strings.

The instructions for this phase are unusually explicit about what *not* to do: no UI, no API,
no crawling changes, **no LLM decisions**, data-driven architecture only. That rules out an
LLM inventing topics, generating question wording at runtime, or deciding which sources are
trustworthy — every decision in this phase had to be either a curated data file or a
deterministic function over one, the same discipline ADR-0025 already applied to the question
catalog and ADR-0026 already applied to the trusted-source catalog.

## Decision

We will, mapping the seven requested deliverables onto data and pure functions:

**1. Domain Ontology Engine — a new pure package, sibling to (not inside) KI-P1/KI-P2.**
`grc_knowledge_ontology` (zero third-party dependencies beyond the already-dependency-free
`grc_knowledge_intelligence`) models `Topic` (a named concept within one of
`KnowledgeDomain`'s existing 11 members — the ontology *elaborates* KI-P1's domains, it does
not invent a second taxonomy), `Clause` and `ContractType` (Contracts' specialized topic
shape, since a contract type's "topics" are the clauses it should contain), and
`Relationship`. `/ontology/<domain>.json` holds the topics for 8 of the 11 domains (Governance,
Risk Management, Compliance, Internal Controls, Audit, Contracts, Data Protection,
Cybersecurity Governance — the ones named explicitly in this phase's requirements);
`/ontology/contracts.json` holds the six requested contract types (NDA, vendor agreement, SaaS
agreement, employment contract, service agreement, procurement contract), each with clauses
categorized `required`/`risk`/`protective` and negotiation points, satisfying "contract
knowledge must include required clauses, risk clauses, ... negotiation points" directly as
curated data.

**2. Expanded question catalog — generated from the ontology by fixed templates, never an
LLM, and never mixed into the hand-curated files.** `question_generation.py` holds a small,
reviewable dict of question templates per domain (e.g. Governance:
`"What {topic} practices should this organization establish?"`,
`"What committees or approvals are required for {topic}?"`; Risk Management:
`"What risks apply to {topic}?"`, `"What controls mitigate risks related to {topic}?"`) plus
four fixed contract templates (required clauses / typical risks / protective clauses /
compliance obligations — the exact four archetypes this phase's examples named).
`generate_ontology_questions` applies these mechanically to every topic and contract type,
producing `KnowledgeQuestion`s namespaced `<domain>.<topic_id>.qN` / `contracts.<type_id>.qN` —
disjoint by construction from the hand-curated catalog's own ids, and verified disjoint by a
test that loads both catalogs and asserts no overlap. This is additive: the 33 hand-curated
questions are untouched, and nothing in `grc_knowledge_intelligence` was modified.

**3. Expanded trusted-source catalog — one real, verified addition; no invented URLs.**
"Do NOT add fake URLs. Only add sources when verifiable" was read literally: `us/nist.json`
adds NIST's Cybersecurity Framework page to the existing `/trusted-sources` catalog (KI-P2's
schema and loader, unchanged) after fetching it live in this session and confirming it is the
genuine, official NIST page. **ISO was deliberately not added** — its site returned HTTP 403
to the fetch tool available in this session, so it could not be independently confirmed live;
adding it anyway on general knowledge alone would be exactly the "unverifiable information"
this requirement forbids. `TrustedSourceType`'s existing five members (regulator, official
framework, standards body, law/regulation, official guidance) already cover "regulators,
standards bodies, frameworks, legal references" from the requirement list; no new source type
was added for "contract references" specifically, since nothing in this session could be
independently verified as a genuine, official contract-reference publisher — the schema
already supports adding one later (e.g. as `standards_body` or `official_guidance`) the moment
a real, verified source exists.

**4. Knowledge relationships — a fixed six-member vocabulary; five kinds illustrated by
curated examples, one kind derived.** `RelationshipType` is a closed enum with exactly the six
edges named: `requirement_to_control`, `control_to_evidence`, `risk_to_control`,
`contract_type_to_clause`, `regulation_to_obligation`, `policy_to_requirement`.
`contract_type_to_clause` is **never hand-authored** — `ontology_catalog._derive_contract_clause_relationships`
computes it directly from the loaded `ContractType`s, so it can never drift out of sync with
the clauses actually modeled. The other five are illustrative example edges in
`/ontology/relationships.json` (e.g. a least-privilege-access requirement satisfied by
role-based access control; that control evidenced by an access review report) — a conceptual
map of *what kinds of things relate to what*, not a live graph over any tenant's actual stored
Controls/Risks/Policies. Building that live graph would mean integrating with the
Controls/Risks/Policies bounded contexts in `packages/domain`, which is out of scope for a
knowledge-representation phase explicitly scoped to data.

**5. Search preparation — richer fields, no retrieval implementation.** `Topic` and
`ContractType` carry `aliases` (synonyms/alternate names), `tags`, and (`Topic` only)
`related_topic_ids` — plain data a future retrieval layer can index against. Every
`related_topic_id` is verified, by test, to resolve to a real topic somewhere in the ontology,
so this search-preparation data can't silently rot into dangling references. No search or
retrieval algorithm is implemented in this phase.

**6. Tests — 27 in `grc_knowledge_ontology`, plus one added to KI-P2's existing trusted-source
tests.** Ontology loading and validation (`test_ontology_catalog.py`, including that the real
`/ontology` directory loads cleanly and every `RelationshipType` is represented), relationship
modeling and derivation (`test_relationships.py`), question generation
(`test_question_generation.py`, including the curated/generated disjointness check), and
missing-clause detection (`test_contracts.py`). `packages/knowledge-research-adapters`'s
existing trusted-source test file gained one more check: every real cataloged source's URL is
`https://`.

**7. Documentation — this ADR and a `PROJECT_STATE.md` update** recording KI-P2 (which had
shipped without a PROJECT_STATE entry) and KI-P3 alongside it.

## Consequences

**Positive**
- The system now has an actual taxonomy to reason from — 37 topics across 7 non-Contracts
  domains, 6 contract types with 38 clauses between them — instead of only the 33 flat,
  hand-written questions KI-P1 shipped with.
- Question-catalog growth is now mostly mechanical: adding one topic to an existing domain's
  JSON file automatically yields 1–2 new, well-formed questions with zero code change, the
  same "data, not code" leverage ADR-0025/0026 already established for their own catalogs.
- `detect_missing_clauses` is a real, tested, deterministic capability — not just descriptive
  data — directly answering "does this contract have the clauses it should."
- Zero new architectural patterns: the pure-package/data-catalog split, the loader shape, and
  the "derive what can be derived, curate what can't" posture all mirror
  `grc_knowledge_intelligence`/`grc_knowledge_research` exactly.
- 28 new/changed tests (27 in `grc_knowledge_ontology`, 1 in
  `grc_knowledge_research_adapters`), all deterministic; nothing requires network, an LLM, or
  a database to pass.

**Negative / costs**
- **Ontology coverage stops at 8 of 11 `KnowledgeDomain`s.** Vendor Management, Policies &
  Procedures, and Regulatory Obligations have no dedicated topic file yet (their ground is
  partly covered by related topics elsewhere — e.g. `risk_management.third_party_risk`,
  `governance.policies_framework`). Growing into them is future editorial work.
- **The relationship examples are illustrative, not a populated live graph.** Five of six
  relationship kinds have only 2–3 hand-authored example edges, referencing example concept
  ids (e.g. `requirement.least_privilege_access`) that are not tied to any real, stored
  Requirement/Control/Evidence/Policy/Regulation record. Wiring the ontology's relationship
  vocabulary to real Controls/Risks/Policies data is explicit future work, not attempted here.
- **The trusted-source addition is narrow (one entry).** ISO, and any other international
  standards body, remains unadded pending a session where it can actually be fetched and
  confirmed — a deliberately conservative choice given this phase's explicit "no fake URLs"
  instruction.
- **No consumer wiring.** Nothing yet calls `generate_ontology_questions` to actually feed the
  KI-P1 gap detector a combined catalog, and nothing calls `detect_missing_clauses` from a
  Tool or agent — this phase delivers the capability and proves it works via tests, the same
  "capability before consumer" scope boundary ADR-0025/0026 both held themselves to.

## Alternatives considered

- **Let an LLM generate the question catalog's wording from the ontology at runtime.**
  Rejected outright — the instructions explicitly forbid LLM decisions in this phase, and
  ADR-0025 already rejected this exact idea for the same reason: a fixed, reviewable template
  set is auditable in a way runtime-generated text is not.
- **Model `Requirement`/`Control`/`Evidence`/`Risk`/`Policy`/`Regulation` as full first-class
  ontology entities (mirroring `Topic`/`ContractType`) instead of opaque labeled ids in
  `Relationship`.** Rejected: those concepts already have real, operational homes in
  `packages/domain`'s Controls/Risks/Policies bounded contexts. Rebuilding lightweight
  duplicates of them here to make `Relationship` "more complete" would be exactly the
  architecture change ("do not force a design", "data-driven architecture only") this phase
  was scoped to avoid; an opaque, labeled edge is enough to prove the relationship vocabulary
  and demonstrate its shape.
- **Add a new `TrustedSourceType` member for "contract references."** Rejected for this
  phase: no genuinely verifiable contract-clause-library source was identified in this
  session to justify it, and the existing five types already cover the other four categories
  named. Adding an enum member with nothing valid to classify under it would be speculative,
  not data-driven.
- **Add ISO anyway, since it is unambiguously a real, well-known standards body.** Rejected:
  the instruction's bar is "verifiable," and this session's tooling could not verify it (HTTP
  403). Treating "I am confident from general knowledge" as equivalent to "I verified this
  now" is exactly the shortcut ADR-0025/0026's "no random blogs, no unverifiable information"
  posture is meant to close off, even when the specific case is very likely correct.
