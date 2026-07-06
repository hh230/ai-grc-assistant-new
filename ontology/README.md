# Domain ontology (as data)

The GRC/Compliance/Governance/Risk/Legal/Contracts taxonomy the Domain Ontology Engine
(Knowledge Intelligence KI-P3, [ADR-0027](../docs/adr/0027-domain-ontology-engine.md)) loads —
**data, not code** (CLAUDE.md §13, the same pattern `/knowledge-catalog`,
`/regulatory-sources`, and `/trusted-sources` already apply). Onboarding a new topic, contract
type, or relationship is a PR that edits one JSON file here — never a code change.

Loaded by `grc_knowledge_ontology.ontology_catalog` into a `DomainOntology`; see that module's
docstring for the canonical schemas.

**Layout:**
- `<domain>.json` (one per `KnowledgeDomain` covered so far) — a list of `topics`, each a named
  concept within that domain (e.g. "board governance" within `governance`).
- `contracts.json` — the Contracts domain's own topic file, using a specialized schema: a list
  of `contract_types`, each carrying the `clauses` a professional reviewer expects it to
  contain (categorized `required` / `risk` / `protective`, with negotiation points).
- `relationships.json` — illustrative example edges for five of the six relationship kinds
  (`requirement_to_control`, `control_to_evidence`, `risk_to_control`,
  `regulation_to_obligation`, `policy_to_requirement`). The sixth kind,
  `contract_type_to_clause`, is never hand-authored here — it is derived automatically from
  `contracts.json` so it can never drift out of sync with the clauses actually modeled.

**Coverage today:** Governance, Risk Management, Compliance, Internal Controls, Audit,
Contracts, Data Protection, and Cybersecurity Governance — 8 of KI-P1's 11
`KnowledgeDomain`s. Vendor Management, Policies & Procedures, and Regulatory Obligations have
no dedicated topic file yet; their ground is already partly covered by the topics above (e.g.
`risk_management.third_party_risk`, `governance.policies_framework`,
`compliance.regulatory_mapping`). Extending coverage to the remaining three, or adding new
topics to an existing domain, is ongoing editorial work — the same posture ADR-0025 already
took for the question catalog's own coverage.

**Relationships are illustrative, not a live graph.** Each entry in `relationships.json`
demonstrates the *kind* of edge the ontology can express, with representative example concept
ids and labels — it is not a populated graph over any tenant's actual stored
Controls/Risks/Policies (those remain `packages/domain`'s Controls/Risks/Policies bounded
contexts, untouched by this phase).

**No fake sources here.** This directory has nothing to do with `/trusted-sources` — it holds
no URLs at all. See `/trusted-sources/README.md` for how cataloged sources are curated and
verified.
