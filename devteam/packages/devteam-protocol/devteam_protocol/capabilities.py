"""AgentCapability + CapabilityResolver — what a step needs, and who provides it (ADR 0063).

AgentCapability is the step-level vocabulary the Foreman writes into PlanStep.tool (ADR 0048):
what a step needs (testing, implementation, review, security, monitoring). It is distinct from
AgentRole (who an agent is) and the mission-level Capability (what a trigger wants).
CapabilityResolver is the separate concern that maps a capability to the agent providing it; the
executor depends on this port, never on concrete agents (amends ADR 0062 rule 6).
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from devteam_protocol.agent import Agent


class AgentCapability(str, Enum):
    """What a plan step needs. A planner (the Foreman, or the AI Organization's CEO) plans in these
    terms; a CapabilityResolver maps each to the agent that provides it. Adding the AI Organization
    is new members here plus new resolver entries — no Core, executor, or registry change (§17)."""

    # The engineering squad's capabilities (ADR 0063).
    TESTING = "testing"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    SECURITY = "security"
    MONITORING = "monitoring"

    # The AI Organization's capabilities (CLAUDE.md §11). The org mission routes through these in
    # order — STRATEGY → ARCHITECTURE → SECURITY_REVIEW → GRC → TESTING → DELIVERY — which the
    # observability adapter maps to CEO → CTO → CISO → GRC Expert → QA → DevTeam. TESTING is reused
    # (the org's QA member is the squad's QA agent). SUPERVISION is the Supervisor's health check.
    STRATEGY = "strategy"
    ARCHITECTURE = "architecture"
    SECURITY_REVIEW = "security_review"
    GRC = "grc"
    DELIVERY = "delivery"
    SUPERVISION = "supervision"


@runtime_checkable
class CapabilityResolver(Protocol):
    """Maps a step's AgentCapability to the agent that provides it (ADR 0063). The Foreman plans
    capabilities; this resolves them; the executor depends only on this port. Raises if a
    capability has no provider, so the engine fails the mission safe."""

    def resolve(self, capability: AgentCapability) -> Agent: ...
