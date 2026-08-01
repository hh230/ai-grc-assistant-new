# V1 Review — Does every screen answer exactly one product question?

> The final review before V1 is called complete (owner, 2026-07-23). Rule 11 says **every view
> answers exactly one product question** — the decision *is* the answer to that question. This page
> audits every V1 screen against its one question. If a screen drifts from its question, this is the
> last chance to clean it before any new feature or V2.

---

## The seven screens, one question each

| Screen | Its one product question | Verdict |
|---|---|---|
| **Dashboard** | *What needs my attention right now?* | ✅ attention-first (Waiting → Running → Failed → recently completed → coverage snapshot); no analytics tiles. |
| **Missions** | *What work exists?* | ✅ the tenant's missions, filterable; a row opens one. Counts are a summary strip, not a second question. |
| **Mission Detail** *(Work Surface)* | *What is happening in this mission?* | ✅ one surface, tabs are views of one state (Summary/Plan/Execution/Evidence/Approvals/Deliverable) — not independent pages. |
| **Result** | *What did this mission produce?* | ✅ a derived decision artifact (Trust Bar → coverage → evidence → gaps → export); "Result", never "Deliverable". |
| **Evidence** | *What evidence do we have?* | ✅ Evidence Collections by kind (the collection is the unit), ingestion status; never a file manager. |
| **Decisions** | *What decisions are waiting for me?* | ✅ a list of **decisions**, not missions (proposed action · mission-as-context · waiting-since · evidence); recent decisions when none wait. |
| **New Mission** | *What work should we start?* | ✅ pick a type + scope → a review station (summary + plan) → Start; no Draft, no auto-run. |

*(Onboarding and the minimal Library/Settings are V1 scaffolding, not primary work screens; each still
answers a single question — "how do I begin?" / "what frameworks exist?" / "who am I?".)*

**Result of the audit: every V1 screen answers exactly one product question.** No screen was found
drifting into a second one. The language is consistent — Result (not Deliverable), Decisions (not
Approvals/Queue), Evidence Collections (not files), Unclassified (not Other), Start (not Run) — and no
screen exposes tools, pipelines, chunks, or step ids.

---

## V1 is architecturally and product-complete

- **Foundation (S1–S4):** the system's language — Read Models · the Application layer + its frozen
  contract (ADR 0054) · Result + Builder/Presenter registries · Evidence + the Reality Gate.
- **Product Expansion (S5–S7):** the language *used, not reinvented* — Dashboard, Decisions (new reads),
  and New Mission (the first behavior: create + start). The whole product surface (S1–S7) is built.
- **The seven methodology guards** held throughout: Product Freeze · Architecture Freeze · Application
  Contract Freeze · Reality Gate · Foundation Reuse · Reuse Ratio · New Component Justification.
- **The thesis proved:** *"Product Expansion adds questions before it adds behavior."* S5/S6 added
  questions (reads); S7 added the one genuinely new behavior (create), on a Core that took it without
  reshaping.

---

## Recommended next step — a V1 Product Review, not V2

Before any new feature or V2, spend a day or two walking the **whole product end to end as a new user,
not as a developer** — from empty workspace → upload evidence → start a mission → review its plan →
run it → read the result → make a decision. That pass usually surfaces small wins in **language,
navigation, and flow** (a confusing label, an extra click, an empty state that feels dead), and this is
the cheapest moment to fix them — before new surface area is added on top. Treat V1 as *complete and
worth polishing*, not *finished and frozen*.
