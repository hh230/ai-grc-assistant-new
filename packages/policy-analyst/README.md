# grc-policy-analyst

Policy Analyst (Policy Intelligence PI-P4, ADR-0021): a **read-only** agent that analyzes one
existing policy's completeness, regulatory alignment, internal consistency, and freshness,
and reports findings with evidence. It never edits, creates, or approves a policy — see
CLAUDE.md §1/§9: an agent proposes, a human decides, and here there isn't even a proposal to
act on, only a report (exactly ADR-0020's Policy Hunter posture, applied to one policy at a
time instead of a tenant-wide scan).

```
one tenant policy (grc_persistence_web.PolicyRepository)
  + confirmed regulatory obligations (grc_persistence_web.RegulatoryObligationRepository)
  -> ReviewPolicyQualityTool (Tool Registry, audited)
  -> quality_engine.review_policy (pure, deterministic, no LLM)
  -> QualityFinding[] (finding type + severity + evidence + citation + recommendation +
                       confidence + related obligation, or none if the policy passes)
```

- `enums.py` — `FindingType` (9 members across the four dimensions below) and `Severity`.
- `models.py` — `PolicyDocument`, `RelatedObligation`, `QualityFinding`,
  `PolicyQualityReport`: plain value objects, independent of
  `grc_persistence_web`/`grc_regulatory_intelligence` types.
- `quality_engine.py` — `review_policy`: **pure, deterministic**, no LLM (CLAUDE.md §1: a
  comparison/detection problem doesn't need a model's free-form guess when a reproducible
  algorithm is available). Four dimensions:
  - **Completeness** — does the body mention each required section at all (purpose, scope,
    ownership, responsibilities, controls, review cycle, exceptions)?
  - **Regulatory alignment** — for every confirmed obligation whose *title* is relevant to
    this policy, how well does the *body* actually cover its text (recall-scored, not
    Jaccard, so a long multi-section body isn't penalized for containing other content)?
    `missing_clause` / `weak_regulatory_coverage` / `outdated_reference`.
  - **Internal consistency** — unclear ownership (`owner_name` blank/placeholder), ambiguous
    language (known weasel phrases), conflicting requirements (the same cadence anchor —
    e.g. "reviewed" — stated with two different frequencies anywhere in the body).
  - **Freshness** — the policy itself is stale (untouched over a year), or a *substantively
    covered* obligation's source regulation was fetched more recently than the policy was
    updated (`policy_older_than_regulation`).
- `ports.py` — `PolicyStore`/`ObligationStore`/`RawDocumentStore`: structural `Protocol`s
  matching `grc_persistence_web`'s repositories exactly, so this package depends on no
  database library at all (the same decoupling ADR-0019/ADR-0020 established).
- `tools.py` — `ReviewPolicyQualityTool` (`review_policy_quality.v1`): a first-class
  `grc_tools.Tool`, `ToolSideEffect.READ_ONLY` (structurally `requires_approval=False`),
  permission-checked (`Permission("policy_analyst")`). The anti-corruption boundary that
  turns concrete records into `models.py`'s plain types before calling `review_policy`.
- `agent.py` — `PolicyAnalystAgent`: calls only its Tool, through the Tool Registry, so every
  invocation is authorized and unconditionally audited exactly like any other Tool call.

**No hallucinated requirements.** Every finding's `evidence` is built from the actual
text/date that triggered it (a missing keyword, a blank owner field, two conflicting
frequency words, a real date comparison) — the engine never invents a requirement that isn't
traceable to the policy or an obligation record.

**Not in this package:** any UI, any write path, and any `apps/api` HTTP endpoint — this phase
builds the agent/Tool as a library, wired and tested via the Tool Registry directly, at the
same scope level PI-P1's classifier Tool and PI-P3's Policy Hunter shipped at. See ADR-0021.
