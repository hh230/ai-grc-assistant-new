# grc-knowledge-ontology

The Domain Ontology Engine (Knowledge Intelligence KI-P3, ADR-0027): teaches the system what
exists in GRC, Compliance, Governance, Risk, Legal, and Contracts — a structured taxonomy of
topics and contract types, the relationships between GRC concepts, and a deterministic
question generator that expands KI-P1's hand-curated question catalog from it.

Flow (CLAUDE.md §5 layering — this package is the pure core; nothing here touches a database,
an LLM SDK, or the network):

```
/ontology/<domain>.json          → ontology_catalog.load_topics_file      → Topic[]
/ontology/contracts.json         → ontology_catalog.load_contract_types_file → ContractType[]
/ontology/relationships.json     → ontology_catalog.load_relationships_file  → Relationship[]
                                    (+ Contract Type → Clause edges, derived from ContractType[])
  ──────────────────────────────────────────────────────────────────────────
                              build_ontology → DomainOntology

DomainOntology → question_generation.generate_ontology_questions → KnowledgeQuestion[]
                 (additive to, and disjoint from, /knowledge-catalog's curated questions)

ContractType + a reviewer's confirmed clause ids → contracts.detect_missing_clauses → Clause[]
```

- `enums.py` — `ClauseCategory` (required/risk/protective), `RelationshipType` (the six kinds
  of edges the ontology can express: requirement→control, control→evidence, risk→control,
  contract type→clause, regulation→obligation, policy→requirement).
- `models.py` — `Topic` (a named concept within a `KnowledgeDomain`, with aliases/tags/related
  topics for future retrieval), `Clause`, `ContractType`, `Relationship`, `DomainOntology`
  (the aggregate, with lookup helpers). Reuses `grc_knowledge_intelligence.KnowledgeDomain`
  rather than inventing a second taxonomy — the ontology *elaborates* KI-P1's 11 domains, it
  does not compete with them.
- `ontology_catalog.py` — loaders mirroring `grc_knowledge_intelligence.question_catalog` and
  `grc_regulatory_intelligence.source_config` exactly (data, not code — CLAUDE.md §13). Contract
  Type → Clause relationships are **derived**, not hand-authored in `relationships.json` — they
  can never drift out of sync with the clauses actually modeled.
- `contracts.py` — `detect_missing_clauses`: pure, deterministic (no LLM) comparison of a
  contract type's required clauses against the clause ids a reviewer confirms are present.
- `question_generation.py` — `generate_ontology_questions`: a small, reviewable set of
  question templates per domain (`_TOPIC_QUESTION_TEMPLATES`) plus four contract-clause
  templates (`_CONTRACT_TYPE_QUESTION_TEMPLATES`), applied mechanically to every topic/contract
  type. No LLM ever invents a question's wording — the templates are the reviewable artifact,
  the same posture ADR-0025 already took for the hand-curated catalog itself.

**No external dependencies** beyond `grc-knowledge-intelligence` (itself dependency-free).

**Not in this package:** a live knowledge graph over a tenant's actual stored
Controls/Risks/Policies (the `Relationship` model is a conceptual map with illustrative
example edges, not a populated operational graph — those bounded contexts remain
`packages/domain`'s own concern); a search/retrieval implementation (the `aliases`/`tags`/
`related_topic_ids` fields are search-preparation data only); any new Tool, API endpoint, or
UI — see ADR-0027.
