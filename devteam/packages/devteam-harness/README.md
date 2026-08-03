# devteam-harness — the AI Test Harness

A permanent QA platform for this product, not a test run. It generates synthetic organizations,
drives them through the real product code, attacks it, and refuses to call anything a pass that it
did not actually verify.

Run it before every release. Change one line anywhere in the product and this should tell you what
broke.

## The one rule everything else follows

**Coverage that did not run is reported, never skipped.**

`apps/web`'s existing eval scripts print `SKIP` and exit `0` when their dependencies are missing,
and CI never sets those dependencies — so `pnpm test` passes today while verifying nothing. Every
design decision in this package is aimed at that failure mode:

- No app running? A finding that says **"HTTP coverage did NOT run. This is not a pass."**
- No browser installed? A finding that says **"browser coverage did NOT run. This is not a pass."**
- Sign-in failed? Every page in that pass is reported as **unchecked**, not passed.
- A page in the inventory 404s? Reported — coverage was silently lost.

A green result from this harness means the checks ran. That is the whole point.

## Surfaces

| Surface | Proves | Needs |
|---|---|---|
| **In-process** | Discovery → Plan behaves correctly across thousands of organizations | nothing |
| **HTTP** (`surfaces/http.py`) | endpoints refuse anonymous callers and don't 5xx | the app running |
| **Browser** (`surfaces/browser.py`) | pages actually **render**, in both locales and both viewports | the app + Chromium |

The browser surface is not redundant with HTTP. A Next.js `error.tsx` boundary returns **HTTP 200**
while displaying "something went wrong" — so a status-code sweep reports a healthy app on a page
the user sees as broken. Every crash this project shipped a fix for recently would have passed the
HTTP sweep and failed the browser sweep.

## The agent team

| Agent | Role |
|---|---|
| **Explorer** | generates untried scenarios and measures whether coverage is still growing |
| **Breaker** | attacks with hostile inputs and protocol abuse |
| **Sentry** | sweeps every protected route as an anonymous caller — the confidentiality check |
| **Pilot** | flies a real browser over every page in `{en, ar} × {desktop, mobile}` |
| **Verifier** | checks results against the invariants |
| **Regression** | replays every seed that has ever failed |
| **Reporter** | classifies findings and writes reproduction steps |

Severity is graded, not uniform. Anonymous data exposure is `CRASH` — in a multi-tenant GRC product
a cross-tenant read is the worst defect that can ship. Console noise is `SUSPICIOUS`. **A harness
that cries wolf trains people to ignore it**, so false positives are treated as defects in the
harness and fixed, not tolerated.

## Running it

```bash
cd devteam/packages/devteam-harness
uv sync
```

Fast, no dependencies — thousands of organizations through the real Discovery engine:

```bash
uv run python -m devteam_harness --count 1000 --db harness.db
```

Reproduce exactly one reported failure (every finding prints this line):

```bash
uv run python -m devteam_harness --seed 412
```

The full team, including the HTTP sweep:

```bash
uv run python -m devteam_harness --team --count 500
```

Add browser coverage — minutes rather than seconds, so it is opt-in:

```bash
uv sync --extra browser && uv run playwright install chromium
uv run python -m devteam_harness --team --browser
```

## Determinism

Every scenario is a seed. The same seed produces the same organization, the same answers, and the
same verdict — so a failure reported by CI reproduces on a laptop from the seed alone, with no
recorded fixtures to go stale. Answers are a *strategy* driven by each question's type and options,
not a script, so the harness keeps working when the interview changes.

## Authentication

The browser sweep signs in as its own account, provisioned once:

```bash
node apps/web/scripts/create-admin.mjs --email harness@rasheed.local \
  --password 'HarnessRun123!' --name 'AI Test Harness' --org 'Harness Test Org'
```

Override with `HARNESS_EMAIL` / `HARNESS_PASSWORD` to point at a CI-seeded user.

## Failure artifacts

On any browser failure the harness writes a bundle beside the run: **screenshot, console, network,
and stack trace**, together. A picture of a broken page without the trace behind it is a bug report
nobody can act on.

Artifacts follow the **finding**, not the verdict — a console error does not make a page unhealthy
but still files a finding, and a finding whose reproduce line points at artifacts that were never
written is a dead end.

## Known failing

`plan_dependencies_exist` fails on roughly 17% of generated organizations: a plan item can depend
on another item that was not scheduled. This is a **real product defect the harness found**, left
red on purpose. Weakening an invariant to make a suite green is how a harness becomes decoration.
