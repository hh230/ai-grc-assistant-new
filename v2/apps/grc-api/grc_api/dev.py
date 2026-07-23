"""A **dev-only** seeded app for local spikes — never a production entry point.

`grc_api:app` is the real (unseeded) ASGI app. This module builds the same app with a handful of
**real** missions driven through the Core engine into the store, and their Mission List projections,
so a local frontend spike exercises both the list *and* the Work Surface (including a mission paused
at a human gate, to demo approve/reject). Run it with: `uvicorn grc_api.dev:app --port 8099`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from document_read_model import DocumentItem, InMemoryDocumentReadModel
from knowledge_runtime import TenantKnowledgeBase
from mission_engine import (
    EchoExecutor,
    InMemoryMissionStore,
    MissionEngine,
    Plan,
    PlanStep,
    StepResult,
)
from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext

from grc_api.app import create_app
from grc_api.document_adapters import DocumentIngestionService

_TENANT_A = TenantContext(tenant_id="tenant-a", principal_id="system")
_TENANT_B = TenantContext(tenant_id="tenant-b", principal_id="system")


def _step(description: str, *, consequential: bool = False) -> PlanStep:
    return PlanStep(description=description, instruction="do", consequential=consequential)


class _ScriptedExecutor:
    """Returns a scripted (output, source_ids) per step — so a gap mission records real control ids
    and evidence, giving its Result a real coverage matrix (echo would produce none)."""

    def __init__(self, scripted: list[tuple[str, tuple[str, ...]]]) -> None:
        self._scripted = scripted
        self._i = 0

    def execute(self, request: Any) -> StepResult:
        output, source_ids = self._scripted[self._i]
        self._i += 1
        return StepResult(step_id=request.step_id, ok=True, output=output, source_ids=source_ids)


class _CitingExecutor:
    """Returns the same citations on every step — so a mission paused at a gate carries evidence,
    and its Decision shows a non-zero evidence count."""

    def __init__(self, citations: tuple[str, ...]) -> None:
        self._citations = citations

    def execute(self, request: Any) -> StepResult:
        return StepResult(
            step_id=request.step_id, ok=True, output="reviewed", citations=self._citations
        )


def _seeded() -> tuple[Any, Any, InMemoryMissionListReadModel]:
    store = InMemoryMissionStore()
    engine = MissionEngine(store, EchoExecutor())
    read_model = InMemoryMissionListReadModel()

    def project(mission: Any, tenant_id: str, mission_type: str, scope: str) -> None:
        read_model.record(
            MissionListItem(
                mission.id,
                tenant_id,
                mission_type,
                scope,
                mission.status.value,
                mission.created_at,
                mission.updated_at,
            )
        )

    # A completed gap assessment, driven with a scripted executor so its Result carries a real gap
    # matrix (A.8.5 covered by evidence, A.8.24 a gap).
    gap_engine = MissionEngine(
        store,
        _ScriptedExecutor(
            [
                (
                    "A.8.5 Secure authentication\nA.8.24 Use of cryptography",
                    ("iso_27001:A.8.5", "iso_27001:A.8.24"),
                ),
                ("Acme implements secure authentication with hardware keys.", ("doc-acme-1",)),
                ("Authentication is covered; cryptography has no supporting evidence.", ()),
            ]
        ),
    )
    m1 = gap_engine.create("gap assessment: Technological", _TENANT_A)
    gap_engine.plan(
        m1,
        Plan(steps=(_step("identify_controls"), _step("gather_evidence"), _step("compute_gap"))),
    )
    gap_engine.execute(m1)
    project(m1, "tenant-a", "gap_assessment", "Technological controls (ISO 27001)")

    # A completed policy draft.
    m2 = engine.create("Draft AUP", _TENANT_A)
    engine.plan(m2, Plan(steps=(_step("Draft policy"),)))
    engine.execute(m2)
    project(m2, "tenant-a", "policy_generator", "Acceptable Use Policy")

    # A mission paused at a human gate: a review step runs (gathering evidence, so the Decision
    # shows an evidence count), then a consequential step pauses. A citing executor gives the review
    # step real citations; approve/resume later runs the gate via the default engine (shared store).
    review = MissionEngine(
        store,
        _CitingExecutor(("access-control-policy.md", "access-review.md", "acme-soc2-typeII.md")),
    )
    m3 = review.create("Publish gap findings", _TENANT_A)
    review.plan(
        m3,
        Plan(steps=(_step("Review controls"), _step("Publish findings", consequential=True))),
    )
    review.execute(m3)  # → AWAITING_APPROVAL
    project(m3, "tenant-a", "gap_assessment", "Vendor Acme review")

    # A decision already made (rejected) — so the Decisions page's "recent" stays alive on first
    # load, before the user acts on anything.
    decided = MissionEngine(store, _CitingExecutor(("aup.md",)))
    md = decided.create("Publish policy exception", _TENANT_A)
    decided.plan(md, Plan(steps=(_step("Review"), _step("Publish", consequential=True))))
    decided.execute(md)  # → AWAITING_APPROVAL
    decided.reject(md, _TENANT_A)  # → CANCELLED (rejected)
    project(md, "tenant-a", "policy_generator", "Policy exception")

    # Another tenant's mission — proves isolation holds through the UI.
    mb = engine.create("Org controls", _TENANT_B)
    engine.plan(mb, Plan(steps=(_step("Collect"),)))
    engine.execute(mb)
    project(mb, "tenant-b", "gap_assessment", "Organizational controls")

    return store, engine, read_model


def _counter_clock() -> Callable[[], float]:
    """A monotonically increasing clock seeded to the last few hours, so seeded uploads get stable,
    ordered, and *realistic* `uploaded_at`s (the view shows "N hours ago", not 1970)."""
    state = {"t": time.time() - 9 * 3600.0}

    def now() -> float:
        state["t"] += 3600.0  # each seed an hour newer than the last
        return state["t"]

    return now


def _seeded_documents() -> tuple[InMemoryDocumentReadModel, TenantKnowledgeBase]:
    """Seed the Knowledge view with a tenant's evidence across several Evidence Collections, plus a
    document mid-ingestion and a failed one, so the local frontend exercises every collection and
    every ingestion status — and a tenant-b document to prove isolation holds through the UI."""
    doc_rm = InMemoryDocumentReadModel()
    kb = TenantKnowledgeBase()
    ingest = DocumentIngestionService(kb, doc_rm, clock=_counter_clock())

    # tenant-a evidence, really ingested → status "ready", spread across collections.
    seeds: list[tuple[str, str, bytes]] = [
        ("access-control-policy.md", "policy", b"Access control policy. Least privilege."),
        ("acceptable-use-policy.md", "policy", b"Acceptable use policy. No credential sharing."),
        ("data-classification.md", "policy", b"Data classification policy. Four tiers."),
        ("incident-response.md", "procedure", b"Incident response. Detect, triage, notify."),
        ("access-review.md", "procedure", b"Quarterly access review and sign-off steps."),
        ("iso-27001-soa.md", "standard", b"Statement of Applicability to ISO 27001 Annex A."),
        ("acme-soc2-typeII.md", "soc_report", b"SOC 2 Type II for Acme Cloud, FY2026."),
        ("risk-register.md", "risk_register", b"Enterprise risk register: 14 risks, owners."),
    ]
    for filename, kind, body in seeds:
        ingest.upload(_TENANT_A, filename=filename, evidence_kind=kind, data=body)

    # The other two ingestion statuses, recorded directly so the view shows them without waiting.
    ingesting_at = time.time() - 300.0
    failed_at = time.time() - 900.0
    doc_rm.record(
        DocumentItem(
            "doc-ingesting", "tenant-a", "vendor.pdf",
            "soc_report", "ingesting", ingesting_at, 91_000,
        )
    )
    doc_rm.record(
        DocumentItem("doc-failed", "tenant-a", "scan.png", "other", "failed", failed_at, 1_200)
    )

    # tenant-b evidence — must never appear for tenant-a in the UI.
    ingest.upload(_TENANT_B, filename="org-policy.md", evidence_kind="policy", data=b"Org policy.")
    return doc_rm, kb


_store, _engine, _read_model = _seeded()
_doc_read_model, _knowledge_base = _seeded_documents()
app = create_app(
    read_model=_read_model,
    mission_store=_store,
    mission_engine=_engine,
    document_read_model=_doc_read_model,
    knowledge_base=_knowledge_base,
)
