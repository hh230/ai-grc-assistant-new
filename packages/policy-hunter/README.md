# grc-policy-hunter

Policy Hunter (Policy Intelligence PI-P3, ADR-0020): a **read-only** agent that compares
confirmed regulatory obligations (PI-P1) against a tenant's policies and reports coverage
gaps with evidence. It never creates, edits, or approves a policy — see CLAUDE.md §1/§9: an
agent proposes, a human decides, and here there isn't even a proposal to act on, only a
report.

```
confirmed regulatory obligations (grc_persistence_web.RegulatoryObligationRepository)
  + tenant policies (grc_persistence_web.PolicyRepository)
  -> ListApplicableObligationsTool / ScanPolicyCoverageGapsTool (Tool Registry, audited)
  -> matching.scan_coverage (pure, deterministic, no LLM)
  -> GapFinding[] (source regulation + citation + confidence + matched policy, or None)
```

- `enums.py` — `GapCategory`: `unmapped_regulatory_obligation`, `missing_required_policy`,
  `incomplete_coverage`, `outdated_policy`.
- `models.py` — `ObligationSummary`, `PolicySummary`, `GapFinding`, `CoverageScanResult`: the
  plain value objects the matching engine operates over, independent of
  `grc_regulatory_intelligence`/`grc_persistence_web` types.
- `matching.py` — `scan_coverage`: a **pure, deterministic** word-overlap comparison, no LLM.
  A gap's confidence score is a property of the match algorithm, not a fabricated model
  confidence — the same inputs always produce the same output (CLAUDE.md §1: no guessing).
- `ports.py` — `ObligationStore`/`RawDocumentStore`/`PolicyStore`: structural `Protocol`s
  matching `grc_persistence_web`'s repositories exactly, so this package depends on no
  database library at all (the same decoupling `grc_regulatory_crawlers.runner` established,
  ADR-0019).
- `tools.py` — `ListApplicableObligationsTool` (`list_applicable_obligations.v1`) and
  `ScanPolicyCoverageGapsTool` (`scan_policy_coverage_gaps.v1`): first-class `grc_tools.Tool`s,
  both `ToolSideEffect.READ_ONLY` (which structurally sets `requires_approval=False` — there
  is nothing to approve). Each is the anti-corruption boundary that turns concrete repository
  records into `models.py`'s plain types before calling `matching.scan_coverage`.
- `agent.py` — `PolicyHunterAgent`: calls only its two Tools, through the Tool Registry, so
  every invocation is authorized and unconditionally audited (CLAUDE.md §19) exactly like any
  other Tool call.

**Why no LLM.** Coverage-gap detection here is a comparison problem (does text A's topic
overlap with text B's), not a generation problem — CLAUDE.md §1's "we would rather say 'I
don't know' than guess" argues for a deterministic algorithm over a model's free-form guess
wherever one is available and sufficient. This also means Policy Hunter's tests need no fake
chat model and can assert exact, reproducible outputs.

**Not in this package:** any UI, any write path, and any `apps/api` HTTP endpoint — this phase
builds the agent/Tools as a library, wired and tested via the Tool Registry directly (the same
scope level PI-P1's classifier Tool shipped at). See ADR-0020 for what's deferred.
