# devteam-dashboard — Operations Dashboard

A **local, presentation-only** web dashboard an operator keeps open during the day to observe the
autonomous dev team, and to approve/reject its proposed fixes. It is a thin view over the **existing
runtime** — it adds no business logic, changes no runtime behavior, touches no deployment, and uses
no database.

## What it shows

- **Overview** — worker state (from `launchctl`), last poll time + monitored repos (from the
  LaunchAgent plist), health, and the live open-PR count.
- **Open Missions** — the actionable set: open PRs with their live CI verdict; a *failing* PR is one
  the daemon opens a gated fix-it mission for. "daemon" columns are parsed from the monitor's log.
- **Mission Details** — click *View* to re-derive that PR's diagnosis + patch **on demand** and
  **Approve** (land) or **Reject** it.
- **Logs** — a live tail of `monitor.err.log`, with search + level filter.
- **Metrics** — today's runbook counters (detected, opened, declined, average attempts, green CI)
  plus Approved/Rejected (the dashboard's own decisions).
- **Settings** — the deployment (read-only), worker status, and GitHub connectivity.

Browser notifications fire when a PR enters the awaiting-approval (failing-CI) set.

## How it integrates (and one honest limitation)

The running monitor (LaunchAgent) keeps its missions in **per-process memory**, so a separate process
cannot read or approve *those* objects. Like `operate.py`, the dashboard therefore **re-derives** a
PR's gated mission on demand through the existing services
(`analyze_run_failure` → `FixItRuntime.open_fix_it`) into its **own** in-memory store, and drives
`ApprovalGateway.approve` / `.reject` on that materialization. The analyzers + AnalysisProposer are
deterministic (LLM-free), so the diff you review is the diff that lands. Consequence: "Open Missions"
is really "open PRs with failing CI", and a mission's id is the dashboard's own materialization (the
daemon's true attempt count is shown as a log-parsed annotation).

All runtime contact is funnelled through one seam — `runtime_gateway.py`. Every other module is pure
presentation (`app.py`), log parsing (`log_reader.py`), plist/launchctl reading (`deployment.py`),
or the dashboard's own decision audit (`actions_log.py`).

> **Approve pushes.** Approving runs the existing gate: `git apply → commit → push → open/refresh PR`.
> It is bound to `127.0.0.1` with no auth — an operator tool for one machine.

## Run

```bash
cd devteam/packages/devteam-dashboard
uv sync
uv run python -m devteam_dashboard
```

Then open <http://127.0.0.1:8787>. With no arguments it reads the live LaunchAgent plist for what to
observe. Overrides: `--repo owner/name`, `--repo-root PATH`, `--log-file PATH`, `--plist PATH`,
`--port N`. It reads `GITHUB_TOKEN` from `<repo-root>/.env` the same way the monitor does.

## Test

```bash
uv run pytest
uv run mypy devteam_dashboard
uv run ruff check
```

Tests use a fake GitHub + fake git runner (no network, no real repo), mirroring the runtime's own
approval tests — the approve path is exercised end to end through the real `ApprovalGateway`.
