# AI GRC Platform — Interaction Principles (V1)

> **What this is.** Ten rules for **how the interface behaves** — the tie-breakers we reach for when two
> screen- or component-level decisions conflict. They are **not** new decisions: each is the behavioral
> distillation of an already-approved one (Vision, Product Spec, Domain Model, IA). *Product Principles
> say what the product **is**; Interaction Principles say how the interface **behaves**.* One page,
> never more than ten. **Sits between the IA (structure) and Screen Flows (behavior).**
>
> **Status:** draft for approval. **Last updated:** 2026-07-20.

---

1. **Everything starts from a Mission.** Any meaningful action creates or continues a Mission; there is
   no "loose" work outside one. *(Founding principle #1 — every piece of work is a Mission.)*

2. **The AI never hides its reasoning path.** The plan, the steps, the sources, and the *why* are always
   viewable — never a black box. *(Product Principle #2 — the product never hides what it is doing.)*

3. **Every recommendation shows its evidence.** No factual GRC claim appears without its citations; the
   user can always open the source. *(Grounding principle — cited, or it says "insufficient evidence".)*

4. **Plans are steerable, not programmable.** The user may remove, reorder, or disable a step — never
   edit its internal logic. *(Product Spec — steering, not programming.)*

5. **Users navigate by work, not by implementation.** The UI is organized around the objects and
   activities of GRC work; implementation concepts (tools, pipeline, chunks) never appear. *(IA founding
   rule + the ❌-visibility exclusions.)*

6. **Deliverables are derived, never edited.** A deliverable is a representation of its mission — viewed
   and exported, not edited in place; to change it, change the mission. *(Domain Model decision.)*

7. **Human approval is explicit.** A consequential action never proceeds silently; it surfaces the
   proposed action with its evidence and waits for a clear decision (who, when). *(Product Principle #4 —
   the human decides.)*

8. **Everything is tenant-scoped.** Every view, search, and action is bound to the current tenant;
   another tenant's data can never appear — the interface fails closed, never leaks. *(Product Principle
   #9 — isolated by construction.)*

9. **The AI explains its uncertainty.** Confidence and thin evidence are shown, not hidden; low
   confidence is surfaced (and, where consequential, gated) rather than presented as certainty. *(Grounding
   + honesty — "insufficient evidence" over a guess; Evidence Mapping ≠ attestation.)*

10. **Time to Deliverable is optimized.** The interface gets the user from *start* to a *meaningful
    deliverable* as fast as possible; long-running work streams progress and **never blocks** the user.
    *(North-star metric + the "fast feel" principle.)*

---

*When a screen or component decision is contested, the answer is here. A proposed interaction that
violates one of these is wrong by definition — change the interaction, not the principle.*
