# worker (app)

Background and scheduled jobs runner; event consumers.

> Deployable process boundary. Real capability lives in `packages/`.

## Knowledge Worker (KI-P4, ADR-0028)

The first real job in this app: `src/grc_worker/knowledge_learning_loop.py` — the
Autonomous Learning Loop. It wires the pure, tested
`grc_knowledge_worker.AutonomousKnowledgeWorker` (question aggregation + scheduler) against
apps/web's live Postgres schema, the Tool-Registry-audited OpenAI synthesizer
(`synthesize_knowledge_answer.v1`), and a real, polite, robots.txt-respecting HTTP research
crawler — then drives it from an actual infinite loop with graceful shutdown on
SIGINT/SIGTERM.

Run it:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aigrc?schema=public \
OPENAI_API_KEY=sk-... \
  uv run python -m grc_worker.knowledge_learning_loop
```

Configuration (all read from the environment — CLAUDE.md §22, no secrets/paths in code):

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `DATABASE_URL` | yes | — | apps/web's Postgres connection string |
| `OPENAI_API_KEY` | yes | — | read by `grc_llm.OpenAISettings.from_env` |
| `GRC_DATA_ROOT` | no | repo root | where `/knowledge-catalog`, `/ontology`, `/trusted-sources` live |
| `GRC_KNOWLEDGE_WORKER_CYCLE_INTERVAL_HOURS` | no | `24` | how often a discovery cycle is due |
| `GRC_KNOWLEDGE_WORKER_POLL_INTERVAL_SECONDS` | no | `3600` | how often the process wakes up to check whether a cycle is due |

All other business logic — gap detection, research planning, extraction validation,
idempotent storage — is reused unmodified from `packages/knowledge-intelligence`,
`packages/knowledge-ontology`, `packages/knowledge-research(-adapters)`, and
`packages/knowledge-worker`. See ADR-0028 for the full design and its explicit boundaries
(no new Tool, no crawler, no API endpoint, no UI).
