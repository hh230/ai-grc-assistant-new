"""`ORG_APPLICABILITY_TOOL` — a pure, tenant-scoped read of a concluded discovery session's Tier B
output (ADR 0066 §3). The Mission never re-evaluates rules; the one-shot analysis already happened,
once, when the session concluded (ADR 0066 §2). Exists mainly for transparency/audit — it makes
the resolved applicability visible as its own Mission step result; `PLAN_DRAFT_TOOL` reads the same
session independently rather than parsing this step's rendered text back out of `prior_context`.
"""

from __future__ import annotations

import json

from governance_store import PostgresGovernanceStore, applicability_to_dict
from pipeline_contracts import TenantContext
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, ToolSpec, ToolStepResult

ORG_APPLICABILITY_TOOL = "org_applicability"


class OrgApplicabilityTool:
    """`payload[PAYLOAD_INSTRUCTION]` is the `discovery_session_id` (mirrors `gap_assessment.py`'s
    reuse of a single scope string across steps)."""

    def __init__(self, store: PostgresGovernanceStore, *, version: int = 1) -> None:
        self._store = store
        self._spec = ToolSpec(
            name=ORG_APPLICABILITY_TOOL,
            version=version,
            description=(
                "Read a concluded discovery session's one-shot analysis result "
                "(frameworks, maturity, capacity, gaps, plan seeds)."
            ),
            side_effect=SideEffectProfile.READ_ONLY,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        session_id = str(payload.get(PAYLOAD_INSTRUCTION, "")).strip()
        if not session_id:
            return _fail("no discovery_session_id given")
        session = self._store.get_session(session_id, tenant.tenant_id)
        if session is None:
            return _fail(f"discovery session not found: {session_id}")
        if session.status != "concluded" or session.applicability is None:
            return _fail("discovery session has not concluded yet")
        rendered = {
            "session_id": session.id,
            "applicability": applicability_to_dict(session.applicability),
        }
        return ToolStepResult(ok=True, output=json.dumps(rendered)).as_payload()


def _fail(reason: str) -> dict[str, object]:
    return ToolStepResult(ok=False, output="", warnings=(reason,)).as_payload()
