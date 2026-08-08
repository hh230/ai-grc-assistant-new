"""`PLAN_FINALIZE_TOOL` — the one CONSEQUENTIAL step (ADR 0066 §3): persists `draft_plan`'s
already-drafted, already human-approved content as a new `GovernancePlan`/`PlanItem` set,
applying §3.1's immutable-snapshot rule (supersede the tenant's current active plan, if any, and
stamp it with the live maturity it actually reached). Never drafts anything itself and never calls
an LLM — by the time this runs, every fact and every word has already been decided and approved;
this step only writes.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable

from governance_discovery.analysis import rate_maturity_scores, score_maturity
from governance_discovery.engine import DiscoveryEngine
from governance_discovery.execution import effective_signals
from governance_discovery.plan import GovernancePlan, PlanItem
from governance_store import PostgresGovernanceStore
from pipeline_contracts import TenantContext
from tool_registry import PAYLOAD_PRIOR_CONTEXT, SideEffectProfile, ToolSpec, ToolStepResult

PLAN_FINALIZE_TOOL = "governance_plan_finalize"

# `pipeline_tool.executor._render_prior_context` renders prior steps as `[Step N]\n<output>`
# blocks joined by a blank line (ADR 0051) — this is the one place that format is parsed back.
_STEP_BLOCK = re.compile(r"\[Step (\d+)\]\n(.*?)(?=\n\n\[Step \d+\]|\Z)", re.DOTALL)


def _extract_last_step_output(prior_context: str) -> str | None:
    blocks = _STEP_BLOCK.findall(prior_context)
    if not blocks:
        return None
    _, content = max(blocks, key=lambda pair: int(pair[0]))
    return content.strip()


class PlanFinalizeTool:
    def __init__(
        self,
        store: PostgresGovernanceStore,
        engine: DiscoveryEngine,
        *,
        version: int = 1,
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._engine = engine
        self._new_id = new_id
        self._now = now
        self._spec = ToolSpec(
            name=PLAN_FINALIZE_TOOL,
            version=version,
            description=(
                "Persist an approved Governance Plan draft as a new immutable plan "
                "version, superseding the previous one."
            ),
            side_effect=SideEffectProfile.CONSEQUENTIAL,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        prior_context = str(payload.get(PAYLOAD_PRIOR_CONTEXT, ""))
        raw_draft = _extract_last_step_output(prior_context)
        if raw_draft is None:
            return _fail("no draft found in prior step results")
        try:
            draft = json.loads(raw_draft)
        except ValueError:
            return _fail("draft step output was not valid JSON")

        now = self._now()
        active_plan = self._store.get_active_plan(tenant.tenant_id)
        new_plan_id = self._new_id()
        version = (active_plan.version + 1) if active_plan is not None else 1

        new_plan = GovernancePlan(
            id=new_plan_id,
            tenant_id=tenant.tenant_id,
            source_session_id=draft.get("source_session_id"),
            source_mission_id=str(payload.get("mission_id", "")),
            status="active",
            version=version,
            previous_plan_id=active_plan.id if active_plan is not None else None,
            inferred_frameworks=tuple(draft.get("inferred_frameworks", ())),
            maturity_baseline=draft.get("maturity_baseline", {}),
            executive_summary=draft.get("executive_summary"),
            top_risks=tuple(draft.get("top_risks", ())),
            created_at=now,
            updated_at=now,
        )

        if active_plan is not None:
            current = self._current_maturity(tenant.tenant_id) or active_plan.maturity_baseline
            superseded = self._store.supersede_plan(
                active_plan.id, tenant.tenant_id, maturity_at_supersession=current, now=now
            )
            if not superseded:
                # A concurrent finalize already superseded it first (Phase 3 hardening) — fail
                # this run cleanly rather than inserting a second "active" plan alongside it, which
                # would silently break the "at most one active plan per tenant" invariant.
                return _fail(
                    f"plan {active_plan.id} was already superseded by a concurrent finalize; "
                    "retry against the tenant's current active plan"
                )

        self._store.create_plan(new_plan)

        for item in draft.get("items", ()):
            item_id = f"{new_plan_id}:{item['id']}"
            depends_on = tuple(
                f"{new_plan_id}:{dep}" for dep in item.get("depends_on_item_ids", ())
            )
            plan_item = PlanItem(
                id=item_id,
                plan_id=new_plan_id,
                tenant_id=tenant.tenant_id,
                pillar=item["pillar"],
                title=item["title"],
                objective=item["objective"],
                # The i18n keys the rule engine emitted, carried through to storage beside the
                # rendered text. The draft already passes them along; this is where they stopped —
                # `finalize` built the PlanItem field by field and simply never mentioned them, so
                # a translatable title reached the database as English prose and nothing else.
                # `.get`, because a draft produced before the keys existed has none.
                title_key=item.get("title_key", ""),
                objective_key=item.get("objective_key", ""),
                expected_outcome=item["expected_outcome"],
                rationale=item["rationale"],
                timeframe_bucket=item["timeframe_bucket"],
                priority=item["priority"],
                effort_size=item.get("effort_size", "medium"),
                depends_on_item_ids=depends_on,
                status="not_started",
                due_at=item.get("due_at"),
                source_signal_keys=tuple(item.get("source_signal_keys", ())),
                source_framework_refs=tuple(item.get("source_framework_refs", ())),
                resolves_signal=item.get("resolves_signal"),
                evidence_ids=(),
                confidence=item.get("confidence"),
                risk_if_skipped=item["risk_if_skipped"],
                created_at=now,
                updated_at=now,
            )
            self._store.create_plan_item(plan_item)

        return ToolStepResult(
            ok=True, output=json.dumps({"plan_id": new_plan_id, "version": version})
        ).as_payload()

    def _current_maturity(self, tenant_id: str) -> dict | None:
        baseline_result = self._store.get_organization_baseline(tenant_id)
        if baseline_result is None:
            return None
        baseline_signals, active_pack_ids = baseline_result
        resolutions = self._store.list_completed_resolutions(tenant_id)
        current_signals = effective_signals(baseline_signals, resolutions)
        active_packs = [
            pack
            for pack in (self._engine.pack_by_id(pid) for pid in active_pack_ids)
            if pack is not None
        ]
        return rate_maturity_scores(score_maturity(current_signals, active_packs))


def _fail(reason: str) -> dict[str, object]:
    return ToolStepResult(ok=False, output="", warnings=(reason,)).as_payload()
