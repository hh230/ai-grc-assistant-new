# Release Process

> Companion to [CLAUDE.md](CLAUDE.md) §23 ("Way of Working"), which states the policy. This
> document is the concrete playbook: the exact commands, settings, and checks that make
> "no direct commits to main" and "ship small, ship safe" actually true in practice, not
> just a stated intention.
>
> **Goal:** new development can never directly affect production users. Every change is
> built on a branch, tested automatically, reviewed by a human, and only then deployed —
> and even after deploy, production data (Supabase) and production traffic are never
> touched by anything running from a branch other than `main`.

---

## 1. Environments

| Environment | Branch | Vercel | Database | Purpose |
|---|---|---|---|---|
| **Production** | `main` | Production deployment (the real domain) | Production Supabase project | Real customers, real data. Nothing reaches this except a merge to `main`. |
| **Preview / Staging** | any feature branch, any open PR | Automatic Preview Deployment (a unique, disposable URL per branch/PR) | A **separate, non-production** Postgres/Supabase project (or a fresh local/CI database) | Where a feature is actually exercised — by CI, by a reviewer, by you — before it can reach real users. |
| **Local development** | your working copy | `next dev`, `pnpm dev` | Local Postgres (Docker) | Day-to-day coding. Matches `.env.local`. |

**Hard rule:** Preview/Staging must never point at the production database or use production
secrets. A bug in a feature branch — including a bad migration — must be physically
incapable of touching real customer data, simply because it's pointed somewhere else.

### Environment variables per environment

See [apps/web/.env.example](apps/web/.env.example) for the full list with descriptions.
What must differ between Production and Preview:

| Variable | Production | Preview |
|---|---|---|
| `DATABASE_URL` | Production Supabase connection string (transaction pooler, port 6543) | A separate staging/preview Postgres — never the production string |
| `SENTRY_DSN` | Set (real project) | **Leave unset.** `NODE_ENV` is `"production"` on *every* Vercel build, including Preview — the only way to stop preview traffic reporting into your production Sentry project is to not give Preview deployments the DSN at all. Configure it in Vercel scoped to the **Production** environment only. |
| `OPENAI_API_KEY` | Production key | Recommended: a separate key (or the same key with a hard budget alert) so a runaway feature branch can't consume production AI spend |
| `RESEND_API_KEY` / `EMAIL_FROM` | Real sending domain | A test/sandbox sender, or leave unset — the app already degrades gracefully (invitation still creates a copyable link if email fails) |
| `AUTH_SECRET` | Production secret (32+ chars, `openssl rand -base64 48`) | A different secret — Preview sessions must never be valid against Production and vice versa |
| `SENTRY_ORG` / `SENTRY_PROJECT` / `SENTRY_AUTH_TOKEN` | Set (enables source-map upload on the Production build) | Unset — build succeeds without them, just without readable stack traces, which doesn't matter since Preview never reports to Sentry anyway |

**Configure this in Vercel**: Project Settings → Environment Variables → for each variable,
use the Production / Preview / Development checkboxes to scope it. Do not rely on a single
value being "fine for both" — the table above is exactly the set where that assumption
breaks.

---

## 2. Git workflow

- `main` is production. It only ever moves forward via a merged, reviewed PR whose CI
  passed. Nobody pushes to it directly — not for a hotfix, not for "just a typo."
- Every change starts on a branch: `feat/<short-name>`, `fix/<short-name>`,
  `chore/<short-name>` (matches CLAUDE.md §23's existing convention).
- Commits use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`,
  `chore:`, `docs:`, `refactor:`, `test:`) — already this repo's convention.

### Enforce it (GitHub branch protection)

This repo does not currently have branch protection configured — I don't have GitHub API
access from this environment to set it up, so this has to be done once, by hand, in the
GitHub UI:

**Settings → Branches → Add branch protection rule** for `main`:
- ✅ Require a pull request before merging (require at least 1 approval)
- ✅ Require status checks to pass before merging — select the CI jobs by name:
  `javascript` and `python` (from [.github/workflows/ci.yml](.github/workflows/ci.yml))
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings (uncheck any "admins can bypass" exemption —
  the whole point is that nobody, including the repo owner, pushes straight to `main`)
- ✅ Restrict force pushes
- ✅ Restrict deletions

Once this is on, `git push origin main` will simply be rejected by GitHub for anyone,
including from this assistant in future sessions — the only path to `main` becomes a PR.

---

## 3. Building a feature

```bash
git checkout main && git pull
git checkout -b feat/my-feature

# ... make changes ...

pnpm --filter @grc/web typecheck
pnpm --filter @grc/web build
pnpm --filter @grc/web test    # real Postgres + real OpenAI calls where relevant — see
                                 # tests/eval/*.eval.ts; each skips cleanly if its
                                 # prerequisite (DATABASE_URL, OPENAI_API_KEY) isn't set

git push -u origin feat/my-feature
```

Push the branch and open a PR against `main` (`gh pr create` or the GitHub UI). This is the
point where a **Preview Deployment** is created automatically (see §5) — a real, working
URL for this exact branch, before anyone approves anything.

---

## 4. Database migrations — test before production, every time

Migrations live in `apps/web/lib/db/migrations/`, applied in filename order by
`node scripts/db-migrate.mjs` (tracked in the `schema_migrations` table, idempotent — safe
to re-run).

**The process, in order:**

1. **Write the migration.** Prefer additive changes (`ADD COLUMN IF NOT EXISTS`,
   `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX CONCURRENTLY IF NOT EXISTS` where locking
   matters) over anything that drops or renames — see `0027_rate_limits_repair.sql` for the
   house style: idempotent, guarded, never destroys existing data even under a schema it
   didn't expect.
2. **Test it locally** against the Docker Postgres every other migration already targets:
   ```bash
   pnpm --filter @grc/web db:migrate
   ```
3. **Test it against Preview/Staging** — apply the same migration file to the
   Preview/Staging database (§1) before it ever reaches production:
   ```bash
   DATABASE_URL="<staging connection string>" node apps/web/scripts/db-migrate.mjs
   ```
   Then exercise the feature against that Preview Deployment, which is already pointed at
   this same staging database.
4. **Backward-compatibility is mandatory.** A Vercel deploy and a database migration are
   *not* atomic — for some window, either old code can run against new schema, or new code
   can run against old schema (e.g. a rollback). A migration that only adds things is safe
   either way. A migration that drops or renames a column the *currently deployed* code
   still reads will break production the instant it runs, independent of when the new code
   ships. If a column truly needs to go, do it in two releases: stop reading/writing it in
   one release, drop it in a later one.
5. **Apply to production** only after the above, once the PR is merged:
   ```bash
   DATABASE_URL="<production connection string>" node apps/web/scripts/db-migrate.mjs
   ```
   This is a manual step today (no CI job runs migrations automatically) — deliberately, so
   a human always makes the call on production schema changes. Run it right after the
   Vercel production deploy for that commit finishes, so the window where new code might
   expect a not-yet-applied column is as short as possible.

---

## 5. Vercel configuration

**Settings → Git**:
- **Production Branch**: `main`. Only a push to `main` (i.e., a merged PR) produces a
  Production deployment.
- **Preview Deployments**: on by default for every other branch and every PR — verify this
  hasn't been disabled under "Ignored Build Step". Every open PR gets its own disposable
  preview URL automatically; that URL is what a reviewer should actually click through
  before approving, not just read the diff.

**Settings → Environment Variables**: scope every variable per §1's table using the
Production / Preview / Development checkboxes — this is the actual mechanism that keeps a
feature branch's Preview Deployment from touching production data, secrets, or the
production Sentry project.

---

## 6. Approving and deploying

1. Open the PR. CI (`.github/workflows/ci.yml`) runs lint, typecheck, tests, and build
   automatically — this must be green.
2. Click through the PR's Preview Deployment URL (posted automatically by Vercel's GitHub
   integration) and actually exercise the change — CI proves the code compiles and unit/eval
   tests pass, not that the feature works end-to-end for a human.
3. At least one reviewer approves, per the branch protection rule in §2.
4. Merge (squash or merge commit, either is fine — this repo doesn't currently mandate one).
5. Vercel deploys `main` to Production automatically on merge.
6. If this PR included a migration, apply it to production now (§4, step 5).
7. Watch Sentry (Production environment) and Vercel's function logs for the next little
   while — this is the fastest signal something's actually wrong, faster than a user report.

### If something goes wrong

- **Bad deploy, no migration involved**: Vercel dashboard → Deployments → find the last good
  one → "Promote to Production". Instant, no git operations needed.
- **Bad deploy with a migration**: this is exactly why §4 insists on backward-compatible,
  additive migrations — rolling back the *code* via "Promote to Production" while the
  *schema* stays on the new (additive) migration should be safe by construction. This is
  also why destructive migrations are two-step (§4.4): a single-step destructive migration
  has no safe rollback path.

---

## Summary checklist

- [ ] Branch off `main`, never commit to it directly
- [ ] `pnpm typecheck && pnpm build && pnpm test` pass locally
- [ ] PR opened; CI green; Preview Deployment clicked through
- [ ] Migration (if any) tested locally, then against Preview/Staging, additive/backward-compatible
- [ ] At least one human approval
- [ ] Merge → Vercel auto-deploys `main` to Production
- [ ] Migration (if any) applied to production right after deploy
- [ ] Watch Sentry/logs post-deploy
