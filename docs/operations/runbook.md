# Autonomous Dev-Team Worker — Operations Runbook

This is the operator's guide for running the autonomous dev-team **Worker** (the continuous
CI-failure fixer, ADR 0061). The system is in **Operation Mode**: it is run on real projects to
gather operational feedback. It does not change code on its own, and it never lands a fix without a
human approval.

> Golden rule: the Worker only *proposes*. It opens a fix-it mission and pauses at a human approval
> gate; a person approves before anything is pushed. No mission touches a repository without you.

---

## What it does (one paragraph)

Every poll it lists the repo's **open pull requests**; for any PR whose latest CI run is **red**, it
downloads the failing job's real log, diagnoses it, and — if it can build a fix — opens a **gated
fix-it mission** with a proposed diff and logs it. You review the diff and, if good, approve it
(`operate --land`), which applies the patch, commits, pushes, and opens/updates the PR. If it can't
build a safe fix, it declines (see §7). One in-flight attempt per PR; after a fix lands it waits for
CI to re-run, and retries up to `--max-attempts` before raising an alert for a human.

---

## Prerequisites

- `uv` installed (the devteam packages run through `uv run --directory …`).
- A local checkout of the target repo. All commands below assume you are at the **repo root**.
- A `.env` file at the repo root containing `GITHUB_TOKEN=…` (see §6 for scopes/renewal).
- `gh` (GitHub CLI) on `PATH` **only for landing** (`operate --land` opens/updates the PR). Reading
  runs/PRs/logs does not need `gh`.

---

## 1. How to run the Worker

```bash
uv run --directory devteam/packages/devteam-runtime \
  python -m devteam_runtime.monitor \
  --repo <owner/name> \
  --repo-root "$(pwd)" \
  2>&1 | tee -a devteam-worker.log
```

Flags:

| Flag | Default | Meaning |
|---|---|---|
| `--repo` | (required) | `owner/name` of the GitHub repo to watch |
| `--repo-root` | `.` | local checkout the diagnosis reads and fixes target |
| `--poll-seconds` | `60` | seconds between passes |
| `--max-attempts` | `3` | fix attempts per PR before it raises an alert |

- It reads `GITHUB_TOKEN` from `<repo-root>/.env` automatically (or from the environment if already
  set — an env var wins over `.env`).
- It logs to stdout; the `tee` above keeps a `devteam-worker.log` you can read (§4).
- **Run it persistently** for a multi-day run with whatever you prefer — a left-open terminal, or
  detached: `nohup <the command above> &` (note the printed PID for §3). A durable service (systemd/
  launchd) is deliberately not set up yet.
- The Worker holds no durable state; it is safe to start/stop/restart at any time (§5).

---

## 2. How to approve a mission (and how to observe without approving)

The Worker **opens and logs** gated missions but does not expose an approval queue (its mission
state is in-memory, per process). You drive review + approval with the **`operate`** CLI, which does
the whole thing in one process.

**Observe only** (read-only — reads logs, shows the diagnosis + proposed diff, stops at the gate):

```bash
uv run --directory devteam/packages/devteam-runtime \
  python -m devteam_runtime.operate \
  --repo <owner/name> \
  --repo-root <checkout-of-the-PR-branch> \
  --run <failing-run-id>          # omit --run to use the latest failure
```

**Approve + land** (your approval — real apply / commit / push / open-or-update PR):

```bash
uv run --directory devteam/packages/devteam-runtime \
  python -m devteam_runtime.operate \
  --repo <owner/name> \
  --repo-root <checkout-of-the-PR-branch> \
  --run <failing-run-id> \
  --land
```

Important:

- **`--repo-root` must be a checkout of the PR's own branch.** The diagnosis reads source from it and
  the patch is committed/pushed from it, so it has to be on the branch you're fixing. (Watching many
  PRs from one checkout works; *landing* a fix needs that PR's branch checked out — a known
  limitation, see the end.)
- `--land` needs `gh` on `PATH` and a token with write scope (§6). Without `--land`, `operate` is
  read-only.
- Find `<failing-run-id>` in the worker log line for that PR, or with
  `gh run list --repo <owner/name>`.

---

## 3. How to stop it

- **Foreground:** press `Ctrl-C` in its terminal.
- **Detached (`nohup … &`):** find and kill the process:

  ```bash
  pgrep -f "devteam_runtime.monitor"          # shows the PID(s)
  kill <PID>                                   # graceful
  kill -9 <PID>                                # only if it will not exit
  ```

Stopping is always safe: the Worker keeps no durable state, and it never leaves a half-applied
change (nothing is pushed without a human `--land`).

---

## 4. How to read the logs (and the operational metrics)

If you started it with `… | tee -a devteam-worker.log`, read `devteam-worker.log`
(`tail -f devteam-worker.log` to follow live). Lines look like:

```
2026-07-29 10:00:00 INFO devteam.monitor: monitoring 2 open PR(s)
2026-07-29 10:00:01 INFO devteam.monitor: PR 7: opened mission mis_abc… (attempt 1) — awaiting_approval
2026-07-29 10:05:00 INFO devteam.monitor: PR 7: CI is green — chain resolved
2026-07-29 10:10:00 WARNING devteam.monitor: chain pr-9 EXHAUSTED after 3 attempt(s): …
```

Reading the 7 metrics off the log:

| Metric | Log signal |
|---|---|
| Failures detected / missions opened | `opened mission … (attempt N)` lines |
| Developer **declined** a patch | those missions logged as `— cancelled` |
| Patches **produced** | those missions logged as `— awaiting_approval` |
| Approvals | your `operate --land` runs (and the PRs they update) |
| CI went **green** | `PR …: CI is green — chain resolved` |
| Attempts needed | the `(attempt N)` counter per PR |
| Needs human intervention | `chain … EXHAUSTED …` (alert) or a `cancelled` mission |

Other lines you may see: `monitor tick failed; continuing` and `advance failed for PR … (…)` are the
Worker surviving a transient error (e.g. a GitHub blip) and moving on — not a crash.

---

## 5. What to do if it stops / crashes

The Worker is a plain `while True: tick(); sleep()` loop with a per-pass safety net, so a single bad
PR or a transient GitHub error is logged and skipped, not fatal. If the **process** is gone
(machine restart, `kill`, or an unexpected fatal error):

1. Check the tail of the log for the cause: `tail -n 50 devteam-worker.log`.
2. If it's a token problem (`Bad credentials` / `requires a token`), renew the token (§6).
3. Just **restart it** with the same command in §1. There is no state to clean up or recover — it
   re-lists the open PRs and continues. Any in-flight mission it had opened is simply re-opened next
   pass if the PR is still red.

---

## 6. How to renew `GITHUB_TOKEN`

The token lives **only** in `<repo-root>/.env` as a single line:

```
GITHUB_TOKEN=github_pat_xxxxxxxx…
```

To renew:

1. Create a new token on GitHub (Settings → Developer settings → Personal access tokens).
   - **Fine-grained**, scoped to the target repo, with: **Actions: Read** (runs + logs),
     **Pull requests: Read & write**, **Contents: Read & write** (write is needed for landing).
   - Or **classic** with the `repo` and `workflow` scopes.
2. Replace the `GITHUB_TOKEN=` value in `<repo-root>/.env`.
3. **Restart the Worker** (§3 then §1) so it picks up the new value. `operate` reads `.env` fresh on
   each run, so it needs no restart.

Notes:

- Never commit `.env` (it is git-ignored) and never paste the token into a shell where it's logged.
- `gh` also authenticates from this same `GITHUB_TOKEN`/`GH_TOKEN`, so renewing it fixes both the
  Worker and `operate --land`.
- Read-only observation (list PRs/runs) works on public repos even without a token, but **downloading
  job logs always needs one** — so a valid token is required for the Worker to diagnose anything.

---

## 7. What to do if the Developer refuses to produce a patch

This is **expected, correct behavior** — not a fault. The Developer declines rather than guess when:

- the error is **structural**, not a single-line fix (e.g. mypy `Duplicate module named …`, which
  needs an `__init__.py` or a rename, not a line suppression), or
- the failure category has **no deterministic fix strategy** yet (today it only auto-fixes Python
  type-check errors with a targeted `# type: ignore[…]`).

When it declines, the mission ends **`cancelled`** with the reason *"human intervention required: the
Developer produced no patch"* — there is **no approval gate** (nothing to approve) and nothing is
pushed. In the log it appears as `PR …: opened mission … — cancelled`.

What to do:

1. Read the mission's **diagnosis** — run `operate` (observe, no `--land`) on that PR's run to see
   the failing file/line and the analyzer's finding.
2. **Fix it by hand** on the PR branch and push. The system correctly identified the problem; a human
   applies the judgement it declined to guess at.
3. If the same *category* of failure keeps needing a human, that is an operational signal worth
   recording — the next fix strategy is prioritized from real occurrences, not anticipation.

---

## Known limitations (current, deferred by design)

Recorded so operators aren't surprised; they are fixed only if real operation makes them worth it:

- **A — watches PRs, not branch pushes.** A red build on a branch with no open PR is ignored.
- **B — single `repo_root`.** One Worker instance diagnoses/lands against one checkout, so *landing*
  a fix for a given PR needs that PR's branch checked out (hence the `operate --repo-root` note in
  §2). Watching is unaffected.
- **C — `open_pr` assumes a new PR.** The landing step opens a PR; for a fix to an *existing* PR the
  push already updates it. Expect friction landing fixes onto pre-existing PRs until this is
  addressed from a real occurrence.
