"""The public entry point. `DecisionEngine.decide(request)` classifies the request and
builds the plan — it decides, it never executes. Deterministic and stateless: the same
request always yields the same plan, and every field is explainable via `plan.reason` and
`plan.matched_cues`.
"""

from __future__ import annotations

from decision_engine.classifier import classify
from decision_engine.models import DecisionPlan, UserRequest
from decision_engine.planner import build_plan


class DecisionEngine:
    def decide(self, request: UserRequest) -> DecisionPlan:
        # A `UserRequest` is required (it carries the tenant, ADR 0040 §4). The old dict-input
        # convenience is gone: a tenant may not be parsed from an untrusted body (§3), so the
        # caller constructs the request — with its tenant — at the trusted boundary.
        classification = classify(request)
        return build_plan(request, classification)
