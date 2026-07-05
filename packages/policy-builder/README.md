# grc-policy-builder

Policy Builder (Policy Intelligence PI-P7, ADR-0024): a **read-only** agent that drafts a
starter policy from one confirmed regulatory obligation, for human review. It never creates,
edits, or approves a policy — see CLAUDE.md §1/§9: an agent proposes, a human decides, and
here the "decision" is a person explicitly saving this draft through the existing,
already-human-gated policy-authoring workflow (`POST /policies` -> `draft`, then the unchanged
`submit-for-review`/`approve`/`publish` lifecycle). This package has no write path at all.

```
one confirmed regulatory obligation (grc_persistence_web.RegulatoryObligationRepository)
  -> DraftPolicyFromObligationTool (Tool Registry, audited)
  -> drafting.draft_policy (pure, deterministic, no LLM)
  -> PolicyDraft (title + body + citation + sections still needing a human's judgment)
```

- `models.py` — `ObligationForDrafting`, `PolicyDraft`: plain value objects, independent of
  `grc_persistence_web` types.
- `drafting.py` — `draft_policy`: **pure, deterministic**, no LLM (the same choice
  ADR-0020/ADR-0021 made for Policy Hunter/Policy Analyst: CLAUDE.md §1 prefers a reproducible
  result over a model's free-form generation wherever one is sufficient). A template, not a
  generator: the *Purpose* section quotes the obligation's own text with a citation; every
  other section (scope, ownership, responsibilities, controls, review cycle, exceptions) is an
  explicit `[Human input required: ...]` placeholder — nothing is invented. The seven sections
  mirror `grc_policy_analyst.quality_engine`'s own completeness check exactly, so a human who
  saves this draft and runs Policy Analyst against it sees precisely the placeholders still
  needing attention, not a false "complete" signal.
- `ports.py` — `ObligationStore`/`RawDocumentStore`: structural `Protocol`s matching
  `grc_persistence_web`'s repositories exactly, so this package depends on no database library
  at all (the same decoupling ADR-0019/ADR-0020/ADR-0021 established). Deliberately **no**
  `PolicyStore` — Policy Builder never reads a tenant's existing policies; whether an
  obligation is already covered is Policy Hunter's question, not this package's.
- `tools.py` — `DraftPolicyFromObligationTool` (`draft_policy_from_obligation.v1`): a
  first-class `grc_tools.Tool`, `ToolSideEffect.READ_ONLY` (structurally
  `requires_approval=False` — there is nothing to gate because there is no write), permission-
  checked (`Permission("policy_builder")`). The anti-corruption boundary that turns the
  concrete obligation record into `models.py`'s plain type before calling `draft_policy`. Only
  ever drafts from a `confirmed` obligation — `pending_review`/`rejected` obligations are
  treated as not found, the same evidentiary bar Policy Hunter and Policy Analyst hold.
- `agent.py` — `PolicyBuilderAgent`: calls only its Tool, through the Tool Registry, so every
  invocation is authorized and unconditionally audited exactly like any other Tool call.

**Human approval before any policy change, by construction, not by a runtime check.** This
Tool cannot write a policy — it has no dependency capable of it. The only path to an actual
`policies` row is a human taking the proposed `title`/`body` and saving it through the
existing creation endpoint, which itself sits behind the unchanged, already-tested
`submit-for-review` -> `approve` -> `publish` human gate. "Do not bypass Policy Hunter/Analyst
boundaries" is satisfied the same way: Policy Builder never re-derives whether an obligation is
covered (Hunter's job) or judges an existing policy's quality (Analyst's job) — it only
transforms one confirmed obligation into a starter draft.

**Not in this package:** any UI, any write path, and any `apps/api` HTTP endpoint — this phase
builds the agent/Tool as a library, wired and tested via the Tool Registry directly, at the
same scope level PI-P3's Policy Hunter and PI-P4's Policy Analyst shipped at. See ADR-0024.
