# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[2.0.0]: https://github.com/hh230/ai-grc-assistant-new/releases/tag/v2.0.0
