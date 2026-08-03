# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.7] — 2026-08-03

### Changed
- **Removed fabricated demo data** — the dashboard and several workspace surfaces
  (Dashboard KPIs/compliance progress/risk distribution/needs attention, Notifications,
  Org Switcher, Evidence, Policies, Regulation Review, Risk Register, AI Worker, Access
  Requests) rendered a static, hardcoded illustrative dataset (`lib/data.ts` — a fictional
  "Acme Financial Group" tenant, a permanently-fixed "1,248 controls", a permanent "2
  unread" notification badge) instead of the current tenant's own data. Every one of these
  now computes from real data and shows an honest empty/loading/error state; `lib/data.ts`
  is deleted.
- Fixed message templates whose placeholders never matched the real values passed to
  them (three `dashboard.needsAttention.*` strings, and all four `dashboard.kpis.*.sub`
  captions, which were plain hardcoded text that silently ignored the real numbers now
  computed for them).

## [2.1.6] — 2026-08-03

### Fixed
- `pdf-lib` moved from `devDependencies` to `dependencies` — it's imported by production code
  (report export), so a production-only install would have been missing it.
- `sanitizeFileName`'s control-character regex now uses `\x00-\x1f` escapes instead of raw
  control bytes (including a literal NUL) embedded in the character class — same matched
  range, but the raw bytes corrupted the file for line-based tools. No behavior change.
- The invite-member endpoint is now rate-limited per account, matching every other
  account-mutating or email-sending route (it was the one gap, and it sends a real email).

### Changed
- The remaining 29 pages using a static, hardcoded `metadata.title` now use the shared
  `pageTitle()` i18n helper, matching the pattern already used by newer pages.

## [2.1.5] — 2026-08-03

### Fixed
- **Root error boundary** — added the `app/global-error.tsx` Next.js requires to catch a crash
  in the root layout itself (an ordinary `error.tsx` can't reach that far); reports to Sentry.

## [2.1.4] — 2026-08-03

### Added
- **Help & Support page** — `/help` now shows a real Help Center (contact support, a link to
  the FAQ, and getting-started shortcuts) instead of the placeholder page.

## [2.1.3] — 2026-08-03

### Added
- **Missions list** — `/missions` now shows a real, DB-backed, tenant-scoped list of governance
  missions (status, awaiting-approval overlay, plan reference) instead of the placeholder page.
  Read-only, backed by the existing `policy_missions`/`policy_mission_steps` tables.

## [2.1.2] — 2026-08-03

### Added
- **Profile + security & access settings** — self-service account management:
  `/profile` (edit display name; session cookie re-issued so the new name/initials
  show immediately) and `/security-access` (change password, requires the current
  password, rate-limited per account). `UserMenu` now links "Profile"/"Security &
  access" to real pages; the dead "Preferences" entry (no backend behind it) is
  removed.

## [2.1.1] — 2026-08-03

### Added
- **Forgot/reset password** — self-service password reset: request a one-time link by email,
  preview which account it belongs to, set a new password. One-time, expiring (1h) tokens
  (256-bit random, only the sha256 hash is ever persisted — `password_reset_tokens`, migration
  `0029`); no user enumeration on the request endpoint; a new link invalidates every prior
  outstanding one; consuming a token is row-locked to prevent concurrent double-use;
  IP+email rate-limited; bilingual (Arabic RTL + English) UI and email. `LoginForm` now links
  to `/forgot-password`.

## [2.1.0] — 2026-08-03

### Added
- **AI Governance Planning Engine** (ADR 0066) — a Discovery → Report → Plan journey that
  determines what compliance frameworks apply to an organization and what to do about it, without
  ever asking the user to name a standard:
  - **Governance Discovery** (`governance-discovery`, `governance-session`, `governance-store`) —
    a two-tier adaptive interview: composable Knowledge Packs (`core`, `technology`,
    `cloud_provider`, …) activate live from typed Signals (boolean/enum/numeric/date/percentage),
    culminating in a one-shot applicability analysis (frameworks, maturity, capacity, gaps, plan
    seeds).
  - **Governance Planning** — a real, human-approval-gated `generate_governance_plan` Mission
    (`resolve_applicability → gather_control_library → draft_plan → finalize_plan`,
    `governance-plan-tools`) produces a ten-section, consulting-style report (Executive Brief,
    Maturity, Critical Gaps, Business Impact, Quick Wins, Priority Roadmap, Timeline, Action
    Tasks, Methodology, Governance Vision) and, on approval, an immutable, versioned governance
    plan (`governance-plan-execution`).
  - **Plan Execution** — a living plan workspace: mark items done/reopened (fully reversible,
    recalculates maturity live), attach optional evidence, full audit trail
    (`governance_plan_events`).
  - **Frontend**: `apps/web` wired to `v2/apps/grc-api` for the first time (ADR 0066 "Frontend
    integration") via an HMAC service-assertion identity bridge; `/discovery` → `/plan` collapsed
    into one product journey with a visible stepper, instead of three disconnected pages.
- `v2/apps/grc-api/README.md` — Install → Migrate → Run instructions (previously undocumented).

### Fixed
- `mission_read_model` (the table `GET /v1/missions` reads) had DDL but no committed `.sql`
  migration — any fresh, non-test deployment's Mission list/read routes 500'd. Added
  `mission-read-model/migrations/0001_mission_read_model.sql`.

## [2.0.0] — 2026-07-31

**V2 COMPLETE — PRODUCTION READY.** The second generation of the Rasheed GRC platform: a frozen,
synchronous, mission-centric Core operated and maintained by an autonomous, human-governed **AI
Organization**. Full detail in [docs/releases/v2.0.0.md](docs/releases/v2.0.0.md).

### Added
- **AI Organization** (`devteam-organization`) — CEO/CTO/CISO/GRC Expert/QA/DevTeam + Supervisor,
  composed on the frozen Core; plans and drives Missions through capability stages with dynamic
  skipping (ADRs 0061–0065).
- **Organization Mission Lifecycle** (ADR 0065) — one operational path: evidence → ownership →
  remediation → verification → closure, with escalation on exhaustion. Certified and **frozen**.
- **Mission Intake & correlation** (ADRs 0063–0064) — normalize heterogeneous triggers into Missions;
  relate a trigger to an existing Mission instead of spawning duplicates.
- **Agent Collaboration Protocol** (ADR 0062) — the boundary is the messages; agents are realizations.
- **Approval domain** (`devteam-approval`) + **Approval API** (`devteam-approval-api`) — generic,
  resumable, durable human-in-the-loop; poll-based review UI.
- **Operations Projection** — one derived `operations.json` per tick; single writer, no dual-write.
- **Operations Dashboard** (`devteam-dashboard`) — read-only viewer: Missions, Agents, Jobs,
  Connectors, Lifecycle, Executive.
- **Connector layer** (11 read-only connectors) and **recurring Jobs** (12) with a strict
  no-fabrication contract — a Mission opens only on real evidence.
- **Live observability** (`devteam-observability`) — journaled, replayable agent activity.
- **CI sweep** — a new workflow job discovers and runs the standalone `v2/` and `devteam/` suites
  (~1,553 tests) that the V1-rooted CI never reached.
- **Architecture Certification** ([docs/devteam/ARCHITECTURE-CERTIFICATION.md](docs/devteam/ARCHITECTURE-CERTIFICATION.md))
  — evidence-based **PASS**; Core declared definitively frozen.

### Changed
- Documentation reconciled with the implemented reality: ADR statuses corrected (0061 → *Accepted —
  implemented*), the ADR index completed (0065 added), and `CLAUDE.md` / `v2/docs/ROADMAP.md` aligned
  with the frozen synchronous Core.

### Frozen
- **v2 Platform + Product Core** — the AI pipeline, `event-bus`, `pipeline-contracts`,
  `mission-engine`, `mission-store` (Slices 1–4), `mission-integration`, and Human Approval
  (Slices 1–3). Frozen 2026-07-17 (ADRs 0035–0055).
- **AI Organization Lifecycle Core** — `LifecycleCoordinator`, Correlation, Strategy & Resolution
  frameworks, the event model, and the composition root. Frozen 2026-07-31 (ADR 0065).

### Deferred (by design, tracked)
- Durable multi-worker mission execution (mission lease, enforced OCC, scheduler) — ADR 0043.
- Advanced Human Approval (quorum / timeout / escalation / SLA) — ADR 0044, Slice 4.
- Enforced RBAC at the application layer; enterprise product surfaces (Workspace UI, notifications).

### Housekeeping
- Removed a tracked stray 0-byte file (`=0.7`); ignored `.env*` and `.vercel`; added dashboard/dev
  launch configurations.

## [v2-phase15-foundation] — prior checkpoint
The accepted V2 baseline (Phase 15 product layer + tenant activation), before the AI Organization phase.

[2.1.7]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.1.7
[2.1.6]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.1.6
[2.1.5]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.1.5
[2.1.4]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.1.4
[2.1.3]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.1.3
[2.1.2]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.1.2
[2.1.1]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.1.1
[2.1.0]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.1.0
[2.0.0]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.0.0
