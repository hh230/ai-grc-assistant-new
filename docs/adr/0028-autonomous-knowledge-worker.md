# ADR 0028: Autonomous Knowledge Worker (KI-P4) — a deterministic scheduler over the already-built gap-research pipeline, and its first real, always-on process

- Status: Accepted
- Date: 2026-07-06
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §1, §5, §7, §9, §11, §12, §13, §16, §19, §20, §22; ADR 0006, 0017, 0018,
  0019, 0025, 0026, 0027

## Context

KI-P1 (ADR-0025) built the question catalog and the deterministic gap detector. KI-P2
(ADR-0026) closed the "who fetches the evidence" gap with a curated trusted-source catalog, a
research coordinator, and `KnowledgeGapResearchRunner` — which already implements "detect
gaps against the stored knowledge base, research each via the trusted-source catalog, store
every grounded result" end to end, fail-safe per question. KI-P3 (ADR-0027) added a Domain
Ontology that can mechanically generate further questions. Every one of those three ADRs
named the same next gap and deferred it in the same words: "no scheduling... no
`apps/worker` cron job... explicit future work," mirroring PI-P2's (ADR-0019) identical
deferral for regulatory crawling.

This phase (Knowledge Intelligence KI-P4) is that future work: the system should periodically
ask itself "what knowledge is missing in Governance, Risk, Compliance, Contracts?", answer
from the two question sources KI-P1/KI-P3 already built, and run the KI-P2 pipeline over
whatever is missing or stale — repeating on a schedule, unattended. Architecture exploration
before writing any code confirmed two things worth naming explicitly: `apps/worker` was a
true empty scaffold (a docstring, nothing else — `apps/worker/src/grc_worker/__init__.py` had
never held any code), and no composition root anywhere in the repository had ever wired a real
database pool, a real LLM provider, and a real HTTP fetcher together into one running process
at the same time — every prior phase's real adapters had only ever been exercised against
fakes in tests. Building this phase's process is therefore the project's first genuinely live,
always-on composition root, not an incremental addition to an existing one.

## Decision

We will, mapping onto the requested loop —

```
Scheduler -> Ontology -> Question Generator -> Gap Detector -> Research Coordinator ->
Trusted Sources -> Knowledge Repository -> repeat
```

— by adding exactly the two links that loop was missing and reusing every other one
unmodified:

**1. Question Generator — merge, don't reinvent.** `packages/knowledge-worker`
(`grc_knowledge_worker`), a new pure package with zero third-party dependencies beyond the
already dependency-free `grc_knowledge_intelligence`/`grc_knowledge_ontology` (the same
posture ADR-0026 held `grc_knowledge_research` to). `question_sources.combine_question_sources`
merges KI-P1's hand-curated catalog with every question KI-P3's ontology can mechanically
generate, defensively raising `ValueError` on an id collision between the two sources —
ADR-0027 already guarantees the ontology's generated ids are namespaced and disjoint from the
curated catalog, but a merge is the one place a violation of that guarantee would actually
surface as a silently dropped or overwritten question, so it is checked here rather than
assumed.

**2. Scheduler — a new, genuinely new concept in this codebase.** `scheduler.LearningCycleScheduler`
is a pure, fixed-interval "is a new discovery cycle due" decision — deliberately distinct from
`grc_knowledge_intelligence.gap_detection`'s own per-question staleness check
(`DEFAULT_MAX_AGE_DAYS`), which answers "is *this answer* stale", not "has it been long enough
since the worker looked at anything at all". No prior phase had built any Clock/Scheduler
concept; this is the first.

**3. Gap Detector / Research Coordinator / Trusted Sources / Knowledge Repository — reused,
not touched.** These four links are exactly `grc_knowledge_research_adapters.
KnowledgeGapResearchRunner` (KI-P2), consumed *structurally* by a new `GapResearchRunnerPort`
Protocol in `worker.py` that matches `KnowledgeGapResearchRunner.run(questions, now=...)`
exactly — the same anti-coupling idiom that runner's own `KnowledgeItemStore` protocol
already uses for `grc_persistence_web`, so `grc_knowledge_worker` never imports the
research/adapters/persistence packages, a network library, or an LLM SDK. Zero changes to
`grc_knowledge_research_adapters`'s actual gap-detection/research/storage logic.

**4. Repeat — a bounded, deterministic loop in the pure package; a real infinite one at the
composition root.** `worker.AutonomousKnowledgeWorker.tick(now=...)` runs one scheduling
decision (skip, or research every actionable gap and advance `last_run_at`).
`run_loop(clock=, sleep=, poll_interval_seconds=, max_iterations=)` repeats `tick` a bounded,
caller-chosen number of times using an injected clock and sleep function — fully
unit-testable with no real time passing. A real always-on process is expected to drive `tick`
itself from its own unbounded loop with real OS signal handling; that loop is not built into
the pure package; see (6).

**5. `last_run_at` stays in-process for this phase.** The scheduler's cadence state lives on
the `AutonomousKnowledgeWorker` instance, not in a new database table. A restart re-triggers
one immediate cycle (`last_run_at=None` means due) rather than resuming exactly where it left
off — an acceptable, explicit tradeoff for this phase (see Consequences) that avoids a new
migration, repository, and persistence pattern for a single timestamp nothing else consumes.

**6. The first real composition root.** `apps/worker/src/grc_worker/knowledge_learning_loop.py`
wires: `grc_persistence_web.Database`/`KnowledgeItemRepository` against apps/web's live
schema (the same one PI-P5/ADR-0022 already reads/writes); `grc_llm.OpenAIChatModel`
(`OpenAISettings.from_env`) registered as `SynthesizeKnowledgeAnswerTool` on a real
`ToolRegistry` with a `PostgresToolInvocationRecorder` — so every synthesis call this process
makes is still authorized, validated, and unconditionally audited exactly like any other Tool
invocation (CLAUDE.md §19), never a second, unaudited path to the LLM; `grc_regulatory_crawlers
.UrllibHttpFetcher` behind `HttpResearchCrawler` (KI-P2's reused-crawler adapter, unchanged);
and `load_questions`/`load_trusted_sources`, which read the real `/knowledge-catalog`,
`/ontology`, and `/trusted-sources` directories from a `GRC_DATA_ROOT` resolved from the
environment (defaulting to the computed repo root) — fail-fast (`WorkerConfigurationError`) if
`DATABASE_URL` is absent or the resolved root doesn't contain the three expected directories,
the same "no secrets/paths hardcoded, config from environment, fail fast" posture
`OpenAISettings.from_env` already established. `main()` builds all of this once, installs
SIGINT/SIGTERM handlers that set an `asyncio.Event`, and calls `run_forever` — a genuinely
unbounded loop (not the pure package's bounded `run_loop`) that additionally catches and logs
any exception a `tick` raises rather than crashing the process (CLAUDE.md §16, fail-safe at
the process boundary — one layer more forgiving than `AutonomousKnowledgeWorker.tick` itself,
which is intentionally strict so a genuine defect in an injected runner still surfaces in
unit tests).

**7. Two pre-existing mypy-strict bugs, found and fixed while wiring the first real
caller.** Every prior phase's structural ports (`StoredKnowledgeItem`, `KnowledgeItemStore`
in `grc_knowledge_research_adapters.runner`) had only ever been type-checked against
hand-written test fakes, never against the real, frozen-dataclass `KnowledgeItemRecord`
flowing through a real `list[...]` return. Two latent incompatibilities surfaced the moment
this phase's composition root passed the real repository to the real runner under
`mypy --strict`: (a) a `Protocol` with plain mutable attributes rejects a frozen-dataclass
implementer outright — mypy requires read-only `@property` members to accept a read-only
field; fixed in `StoredKnowledgeItem`, and mirrored in this package's own new
`GapResearchOutcomeLike`, which has the identical shape for the identical reason
(`GapResearchOutcome` is also a frozen dataclass); (b) `list[StoredKnowledgeItem]` is
invariant, so a concrete `list[KnowledgeItemRecord]` — a subtype, not the same type — could
never satisfy it; fixed by widening `KnowledgeItemStore.list_all`'s return type to the
covariant `Sequence[StoredKnowledgeItem]`. Both fixes are additive-only (Protocol shape
only), verified not to change `grc_knowledge_research_adapters`'s own 22 existing tests'
behavior. `packages/llm` was also missing its `py.typed` marker (every sibling package has
one) — added, since nothing importing `grc_llm` under `mypy --strict` had existed before this
phase's composition root either.

## Consequences

**Positive**
- Closes every named deferral across ADR-0019/25/26/27 ("no scheduling... explicit future
  work") with the actual missing pieces — a scheduler and a merged question source — rather
  than re-litigating any already-built stage.
- The pure `grc_knowledge_worker` package stays as dependency-free and structurally-decoupled
  as its KI-P2/KI-P3 predecessors: it depends on nothing beyond
  `grc_knowledge_intelligence`/`grc_knowledge_ontology`, and the real research runner is
  injected through a Protocol, never imported.
- This is the first component in the entire Knowledge Intelligence (and indeed Policy
  Intelligence/Regulatory Intelligence) line to be exercised as a real, always-on process
  wiring a real database, a real LLM provider, and real network I/O together — and the act of
  wiring it surfaced and fixed two real, previously-undetected mypy-strict gaps in
  already-shipped code (§7), which a fakes-only test suite could never have caught.
- 26 new tests (17 pure `grc_knowledge_worker` — question merging, scheduler cadence, tick/
  run_loop semantics — plus 9 composition-root tests: real data loading with no network,
  environment-driven configuration and its fail-fast paths, and `run_forever`'s stop/skip/tick/
  survive-an-exception semantics against a fake runner), all deterministic; nothing in the
  automated suite opens a real database connection, makes a real HTTP request, or calls a
  real LLM.

**Negative / costs**
- **No durable `last_run_at`.** A process restart forgets when it last ran and treats the next
  tick as immediately due. Acceptable for a first version — the underlying gap detection is
  itself idempotent and safe to re-run — but a genuinely unattended, rarely-restarted
  deployment may want this persisted. Explicit future work if the in-process behavior proves
  insufficient; would be an additive migration (a single timestamp row), not a redesign.
- **No container wiring.** `docker/worker.Dockerfile` is left as the scaffold placeholder it
  already was, deliberately consistent with `docker/api.Dockerfile`'s own precedent (still a
  placeholder despite `apps/api` carrying five ADR phases of real code) — Dockerfile/deployment
  wiring is treated as its own separate concern in this repo, not bundled with a feature phase.
- **No opt-in live integration test.** Unlike `grc_llm`'s `test_openai_live.py`
  (`RUN_LLM_LIVE_TESTS=1`), this phase does not add a live, real-network/real-database/
  real-LLM smoke test for the composition root, to avoid an uncontrolled-cost, potentially
  slow, network-dependent test being added silently as part of an otherwise deterministic
  suite. Verifying the real process end to end against a real Postgres + `OPENAI_API_KEY`
  remains a manual/ops verification step (documented in `apps/worker/README.md`), the same
  boundary PI-P6 (ADR-0023) already drew for its own live proxy check.
- **Still no consumer wiring, no API endpoint, no UI.** Explicitly out of scope, matching every
  prior Knowledge Intelligence phase's own boundary.

## Alternatives considered

- **Fold the scheduler directly into `KnowledgeGapResearchRunner`.** Rejected: that runner's
  job is "detect gaps and research them once, given a question set" — genuinely reusable by
  a future API-triggered manual run, a Workflow Engine step, or a test, none of which want a
  cadence decision baked in. Keeping "when to run" (this phase) separate from "what to do when
  it runs" (KI-P2, unmodified) is the same separation of concerns CLAUDE.md §6 already asks
  for between orchestration and business capability.
- **Persist `last_run_at` in a new table now, rather than in-process.** Rejected for this
  phase's scope: nothing yet needs cross-restart cadence precision, and a new migration for a
  single timestamp is the kind of premature persistence CLAUDE.md's coding standards
  explicitly discourage ("don't add abstractions beyond what the task requires"). Named
  explicitly as future work instead of silently omitted.
- **Give the pure `AutonomousKnowledgeWorker.run_loop` a real, unbounded `while True`.**
  Rejected: an unbounded loop with no `max_iterations` cannot be driven deterministically by a
  test without either mocking `asyncio.sleep` in a way that fights the event loop or accepting
  a genuinely flaky/slow suite. Bounding it and building the *real* infinite loop (with OS
  signal handling) only at the composition root — where it belongs, since only a deployed
  process actually needs to run forever — keeps the reusable package itself fully
  deterministic.
- **Let the composition root's `run_forever` propagate a tick's exception and let the process
  crash (relying on an external supervisor like systemd/Docker to restart it).** Rejected in
  favor of catching and logging: a supervisor-restart strategy would also discard the
  in-process `last_run_at` on every transient failure (e.g. one flaky DNS lookup during
  crawling), repeatedly re-triggering a full cycle instead of simply retrying at the next
  scheduled poll. Catching keeps the common case (a transient, isolated failure) cheap and
  makes a genuinely fatal condition (e.g. `WorkerConfigurationError` at startup, before the
  loop begins) still fail loudly, since only `run_forever`'s own loop body is guarded, not
  `main()`'s setup.
- **Silently leave the two mypy-strict Protocol bugs (§7 above) unfixed and instead route
  around them in the composition root (e.g. with `# type: ignore`).** Rejected: CLAUDE.md's
  Definition of Done requires "type-check... pass with no new warnings," and a targeted,
  additive Protocol-shape fix (read-only properties; a covariant `Sequence` return type) is
  safer and more honest than suppressing a real structural mismatch mypy had correctly found.
