"""`ORG_APPLICABILITY_TOOL` — a pure, tenant-scoped read of the analysis a plan will be built on.

The Mission never re-evaluates rules; the analysis already happened, once, and was RECORDED
(ADR 0066 §2, ADR 0068 §D5). What it reads is the newest `session_applicability_versions` row:

    discovery-only session  -> v1, written when the interview concluded
    sector-concluded session -> v2, written when the sector assessment concluded

Not `session.applicability`. That column holds the CORE analysis and nothing updates it when a
sector answer changes a decision — reading it meant the sector channel could compute a v2 that
nothing ever looked at. The column stays as it is (v2 is never written back into it): the version
table is where the answer lives now, and the column remains the record of what discovery alone
concluded.

`PLAN_DRAFT_TOOL` reads the same version independently rather than parsing this step's rendered
text back out of `prior_context`.
"""

from __future__ import annotations

import json

from governance_store import PostgresGovernanceStore
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
        if session.status != "concluded":
            return _fail("discovery session has not concluded yet")
        version = self._store.latest_applicability_version(session_id, tenant.tenant_id)
        if version is None:
            # A session concluded before ADR 0068 and never backfilled. Refused rather than fallen
            # back to `session.applicability`: a silent fallback is how the two would drift apart
            # without anyone noticing which one a plan was built on.
            return _fail(
                f"no recorded applicability version for session {session_id} — run "
                "`python -m grc_api.backfill_applicability`"
            )
        rendered = {
            "session_id": session.id,
            "applicability_version_id": version["id"],
            "applicability_version": version["version"],
            "applicability": version["applicability"],
        }
        return ToolStepResult(ok=True, output=json.dumps(rendered)).as_payload()


def _fail(reason: str) -> dict[str, object]:
    return ToolStepResult(ok=False, output="", warnings=(reason,)).as_payload()
