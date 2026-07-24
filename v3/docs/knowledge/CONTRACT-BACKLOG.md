# V3 Canonical Model — Contract Backlog (deferred amendment proposals)

> These are **consciously deferred** ideas for **future** versions of the ratified contract
> ([`CANONICAL-MODEL.md`](./CANONICAL-MODEL.md)). They are **NOT part of the frozen contract** and
> **must not be implemented during Stage 2.** Each becomes an amendment only when a **real need**
> appears and the owner approves a new contract version. Recording them here keeps the contract
> stable while ensuring good ideas are not lost.

---

## BL-1 · Provenance / Lineage on Entities and Relationships

- **Proposed for:** Contract **v1.3** · **Target stage:** Stage 5 (Validation) / Stage 6 (Persistence)
- **Trigger to activate:** once Tier-2 Entity Relationships exist and are being reviewed, or when
  the AI/LLM begins generating relationships that must be audited.
- **Idea:** every Entity and every Relationship records **exactly where it came from** — not just
  the Source ID, but full lineage:
  - *Entity provenance:* `Source` (e.g. `ISO-27001@2022`) · `Location` (e.g. `Clause 6.1.2`) ·
    `Paragraph` · `Extraction` (pipeline version) · `Extractor` (which parser) · `Confidence`.
  - *Relationship provenance:* `Relation` (e.g. `maps_to`) · `Derived-by` (**Human / LLM /
    Rule-Engine**) · `Evidence` · `Confidence`.
- **Nature:** *not* a new independent axis like Authority or Stability — it is the **lineage of
  proof** (Provenance). It is the "where/how did this come from" companion to Principle 11's
  Temporal Traceability ("as of when").
- **Relation to existing contract:** deepens §4.2 (Tier-2 edges are already "provenance-bearing")
  and §10.11 (Principle 11). No conflict — purely additive.
- **Why deferred:** the contract is frozen through Stage 2 by owner rule. This is a conscious v1.3
  decision to be made **after a real need surfaces at review/AI-generation time**, never a
  mid-execution change.

*(Owner-raised this session, 2026-07-24. Do not implement until a v1.3 amendment is explicitly
approved.)*
