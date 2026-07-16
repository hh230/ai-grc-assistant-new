# answer-validation

Checks a generated `Answer` against the context it was supposed to be grounded in and the
`ResponseContract` it was supposed to satisfy.

```
Answer + ContextPackage + ResponseContract  →  ValidatedAnswer
```

Depends only on `pipeline-contracts`.

## What it does — and pointedly does not

It **only validates**. It never generates, never retrieves, never extracts citations from the
model, and never mutates the answer: `ValidatedAnswer.answer` is the *same object* that came
out of generation, wrapped with a verdict.

It also never fails a run. A poor answer is **reported, not suppressed** — the orchestrator
records the verdict on the `PipelineResult` and surfaces the issues as warnings. Deciding what
to do about a bad answer belongs to the caller.

Checks are **deterministic and structural**. Semantic prohibitions (a contract's
`forbidden_outputs` — "legal advice", "definitive certification of compliance") are *not*
adjudicated here: judging whether prose constitutes legal advice needs a reviewer phase, and
pretending a regex does it would be worse than not checking. Do not assume this engine catches
prohibited content.

## The verdict

```
ValidatedAnswer
  ├─ answer                 the original Answer (identity preserved — never copied/edited)
  ├─ status                 passed | warnings | failed
  ├─ issues[]               ValidationIssue(code, severity, message, detail)
  └─ confidence_adjustment  a SUGGESTED downward nudge (≤ 0) — applied by nobody here
```

`is_valid` is true unless a hard error was found; warnings do not disqualify an answer.

## The checks

| Code | Severity | Catches |
|---|---|---|
| `empty_answer` | error | the model returned nothing |
| `missing_citations` | error | citations required, evidence existed, none cited |
| `unknown_citation` | error | cites `[S<n>]` that is absent from the `ContextPackage` — **fabrication** |
| `malformed_citation` | warning | a marker that isn't the `[S<n>]` style |
| `missing_confidence` | warning | the contract requires a stated confidence, the answer has none |
| `unsupported_confidence` | warning | a stated confidence that isn't high/medium/low |
| `missing_section` | warning | a required section heading is absent |

The two error-level citation checks are the point of the package: under CLAUDE.md §12/§19 an
uncited or fabricated citation on a compliance matter is not a formatting slip, it is the
failure mode the whole grounding architecture exists to prevent.

`ConfidencePenalty` makes the adjustment policy explicit and injectable rather than scattering
magic numbers through the validator.

## Wiring

Opt-in. With no validator injected the pipeline runs exactly as it did before this package
existed, and `PipelineResult.validated` is `None`.

```python
AIOrchestrator(..., answer_validator=AnswerValidator())
```

When wired, it publishes `AnswerValidated` onto the event bus, which enriches the audit
record with the verdict. When it isn't, the audit record says `validation_status =
"not_configured"` — an explicit fact, not a silent pass.

## Related

- [ADR 0039](../../../docs/adr/0039-v2-platform-hardening.md) — this package's decision
- [Platform hardening architecture](../../docs/architecture/platform-hardening.md) §1
