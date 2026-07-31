# AI GRC Product — Charter (v1)

> ## The platform is no longer the product. The product is no longer the platform.

This opens the **AI GRC Product** phase. The DevTeam Platform is frozen at v1.0 (Runtime,
Observability, Dashboard API, DevTeam Ops — see
[../devteam/ARCHITECTURE-HANDOFF.md](../devteam/ARCHITECTURE-HANDOFF.md)). From here on, success is
**not** measured by the number of APIs, dashboards, or agents. It is measured by one thing:

> **How well a GRC officer can complete a complex mission — quickly, transparently, and with confidence — using the platform we built.**

---

## The Governance Gate

Before accepting **any** Story, Feature, or Refactor, ask these in order. Stop at the first "no".

**Gate 1 — User Value.**
Does this solve a real problem for a GRC user? If the answer is *"no"* or *"not yet"* — **do not build it.**

**Gate 2 — Platform Dependency.**
Can it be done with the current DevTeam platform? If *"yes"* — then **no changes to Runtime,
Observability, or `RuntimeStateView` are permitted.** Build it in the product layer.

**Gate 3 — Platform Change.**
If *"no"* (it genuinely cannot be built on the platform as-is), then — and only then:
1. Name the **real constraint** in the platform.
2. **Document** the constraint.
3. **Prove** it blocks a product feature (not a hypothetical).
4. Make the **smallest possible** change.
5. **Record an ADR** — because it broke part of the Freeze.

Never the reverse. We do not loosen the Freeze first and justify it later.

**Gate 4 — Product Simplicity.**
When two solutions exist — one that adds **platform** complexity, one that adds a little **product**
complexity — usually choose the **product** one. The platform lives for years; product pages change
constantly. Keep the durable thing simple; let the changeable thing absorb the churn.

---

## Mission-first, not module-first

Do not start an experience by asking *"How do we build the Risk Experience?"*
Start by asking:

> **"What Mission does the GRC officer want to accomplish?"**

For example:

- Assess ISO 27001 readiness
- Perform a vendor risk assessment
- Create a new policy
- Review evidence
- Prepare an audit package
- Investigate a compliance gap

The architecture then follows the mission, not the org chart:

```
        Mission  ("Assess ISO 27001 readiness")
           │
           ▼
      AI Orchestrator
           │
   ┌───────┼───────┬───────┬───────┬────────┐
   ▼       ▼       ▼       ▼       ▼        ▼
Knowledge Compliance Risk  Policy  Report  Workflow
```

**Not** a catalog of `Risk Module`, `Compliance Module`, `Policy Module` bolted side by side.

This is the same **Mission-Centric UX** that made the DevTeam platform work — now applied to the GRC
user instead of the platform operator. It is also exactly what the engineering constitution already
prescribes: **CLAUDE.md §7 (the AI Orchestrator is the brain), §8 (Mission-Centric design), §11 (the
Knowledge / Compliance / Risk / Policy / Report / Workflow agent roster).** We are not inventing a new
architecture here — we are finally executing the one the project was founded on.

---

## How the first experience begins

Not with pages or schemas. The disciplined first move mirrors how each platform layer began:

1. **Reality Gate** — what is actually true today (data, frameworks, constraints)?
2. **Product Question** — what mission does the GRC officer need to complete, and what does "done, with confidence" look like for them?
3. Only then: the mission's plan, the agents it composes, and the workspace it surfaces in.

Every step back through the four gates.

*This charter governs the AI GRC Product phase. The frozen platform underneath it
([ARCHITECTURE-HANDOFF.md](../devteam/ARCHITECTURE-HANDOFF.md)) is the foundation, not the subject.*
