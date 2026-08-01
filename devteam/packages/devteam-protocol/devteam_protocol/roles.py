"""``AgentRole`` — the fixed agent-collaboration vocabulary (ADR 0061; CLAUDE.md §11).

A role is *who* a message is from or to, kept as data so a planner can route work and specialists
can declare their identity without importing one another. This realizes the §11 multi-agent pattern;
a new role is added here and registered, never by editing the Core (§17).

Two cohorts share this one vocabulary (both run on the frozen Core, both observed the same way):

- **The engineering squad (ADR 0061)** — Foreman, QA, Monitor, Security, Developer, Reviewer: the
  platform-engineering agents that watch CI and land fixes.
- **The AI Organization (CLAUDE.md §11)** — CEO, CTO, CISO, GRC Expert, DevTeam, Supervisor: the
  permanent organization that governs missions end-to-end (understand → architect → secure →
  assess → verify → deliver), supervised for liveness. QA is shared — the organization's quality
  member IS the engineering squad's QA agent, reused, not duplicated.
"""

from __future__ import annotations

from enum import Enum


class AgentRole(str, Enum):
    # The engineering squad (ADR 0061).
    FOREMAN = "foreman"      # plans & routes dev missions, follows up, escalates
    QA = "qa"                # runs/authors tests, smoke-tests the running app, verifies fixes
    MONITOR = "monitor"      # watches logs/errors/CI/performance, raises findings
    SECURITY = "security"    # dependency/secret scanning, SAST-lite, tenancy/authz review
    DEVELOPER = "developer"  # diagnoses and proposes a patch — never lands it itself
    REVIEWER = "reviewer"    # reviews diffs against the pillars, tests, and security

    # The AI Organization (CLAUDE.md §11) — the permanent, mission-governing organization.
    CEO = "ceo"              # understands the mission, sets strategy, delegates, approves direction
    CTO = "cto"              # technical planning, architecture, decomposition, engineering review
    CISO = "ciso"            # security review, threat analysis, compliance validation, sign-off
    GRC_EXPERT = "grc_expert"  # ISO/NIST/SOC2/PCI/GDPR mapping, policy, risk, evidence, controls
    DEVTEAM = "devteam"      # consolidates the org's plan into delivery; defers landing to the gate
    SUPERVISOR = "supervisor"  # health, heartbeat, stalled-mission detection, recovery — above all
