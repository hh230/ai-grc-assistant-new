"""Retrieval and decision contract behaviour: the metadata filter, the query defaults, the
intent coercion on a plan, and the wire shapes the rest of the pipeline reads.
"""

from __future__ import annotations

import json

import pytest
from pipeline_contracts import (
    DEFAULT_TOP_K,
    DecisionPlan,
    Filter,
    Intent,
    RetrievalFilter,
    RetrievalQuery,
    RetrievedChunk,
    RetrievedContext,
    TenantContext,
    UserRequest,
    build_citation,
)

from tests.conftest import make_chunk


def make_retrieved(chunk_id: str = "c1", confidence: float = 0.8) -> RetrievedChunk:
    chunk = make_chunk(chunk_id=chunk_id)
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        text=chunk.text,
        citation=build_citation(chunk),
        document_profile=chunk.document_profile,
        structure_profile=chunk.structure_profile,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        scores={"vector": 0.9, "keyword": 0.4},
        confidence=confidence,
    )


# ── Filter ────────────────────────────────────────────────────────────────────
def test_a_filter_with_no_facets_set_is_empty():
    assert Filter().is_empty()


def test_any_single_facet_makes_a_filter_non_empty():
    """`is_empty` decides whether a provider can skip predicate work entirely, so every
    facet has to count — one missed field would silently widen the search."""
    assert not Filter(document_profiles=("law",)).is_empty()
    assert not Filter(categories=("laws",)).is_empty()
    assert not Filter(structure_profiles=("regulation_article",)).is_empty()
    assert not Filter(languages=("ar",)).is_empty()
    assert not Filter(document_ids=("doc-1",)).is_empty()
    assert not Filter(codes=("5-1",)).is_empty()


def test_retrieval_filter_is_the_same_contract_under_the_pipeline_wide_name():
    assert RetrievalFilter is Filter


# ── RetrievalQuery ────────────────────────────────────────────────────────────
def test_a_query_needs_only_text_and_defaults_the_rest():
    query = RetrievalQuery(text="What does PDPL require?")
    assert query.top_k == DEFAULT_TOP_K
    assert query.filter.is_empty()
    assert query.language is None
    assert query.codes == ()
    assert query.weights is None


def test_two_default_queries_do_not_share_a_filter_instance():
    assert RetrievalQuery(text="a").filter is not RetrievalQuery(text="b").filter


# ── RetrievedContext ──────────────────────────────────────────────────────────
def test_retrieved_context_defaults_to_no_warnings_or_timings():
    context = RetrievedContext(
        query="q", results=[], total_candidates=0, applied_filter=Filter(), overall_confidence=0.0,
    )
    assert context.warnings == []
    assert context.timings_ms == {}


def test_retrieved_context_serializes_its_chunks_and_citations():
    context = RetrievedContext(
        query="q", results=[make_retrieved()], total_candidates=40,
        applied_filter=Filter(document_profiles=("law",)), overall_confidence=0.72,
        warnings=["thin evidence"], timings_ms={"vector": 1.5},
    )
    data = context.to_dict()
    assert data["total_candidates"] == 40
    assert data["results"][0]["citation"]["formatted"].startswith("pdpl.pdf")
    assert data["results"][0]["scores"] == {"vector": 0.9, "keyword": 0.4}
    assert data["warnings"] == ["thin evidence"]
    json.dumps(data)


def test_the_applied_filter_keeps_its_historic_raw_shape_with_tuples_intact():
    """Deliberately not run through `to_plain`: the filter echoes back exactly as applied,
    tuples and all, which is what existing consumers read."""
    context = RetrievedContext(
        query="q", results=[], total_candidates=0,
        applied_filter=Filter(document_profiles=("law", "regulation")), overall_confidence=0.0,
    )
    assert context.to_dict()["applied_filter"]["document_profiles"] == ("law", "regulation")


# ── UserRequest ───────────────────────────────────────────────────────────────
_T = TenantContext(tenant_id="org_acme", principal_id="u1")


def test_the_minimal_request_shape_works():
    assert UserRequest.from_dict({"query": "hello"}, tenant=_T) == UserRequest(
        query="hello", tenant=_T, has_document=False
    )


def test_from_dict_coerces_and_survives_a_junk_payload():
    """The entry boundary: an API caller's dict is untrusted input, not a contract."""
    assert UserRequest.from_dict({}, tenant=_T) == UserRequest(query="", tenant=_T)
    assert UserRequest.from_dict({"query": 5, "has_document": "yes"}, tenant=_T) == UserRequest(
        "5", _T, True
    )


def test_tenant_is_required_and_never_comes_from_the_payload():
    # tenant is a required, keyword-only argument to from_dict — never read from `data`
    # (ADR 0040 §3: the request body may not name a tenant).
    with pytest.raises(TypeError):
        UserRequest.from_dict({"query": "x", "tenant": "org_evil"})  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        UserRequest(query="x")  # type: ignore[call-arg]  # tenant is required


# ── DecisionPlan ──────────────────────────────────────────────────────────────
def make_plan(intent, **overrides) -> DecisionPlan:
    defaults = dict(
        intent=intent, workflow="lookup_workflow", requires_retrieval=True,
        requires_document=False, requires_reranker=False, requires_human_gate=False,
        multi_step=False, retrieval_passes=1, context_budget=5, target_profiles=["law"],
        confidence=0.9, reason="matched cue",
    )
    defaults.update(overrides)
    return DecisionPlan(**defaults)


def test_a_plan_built_from_strings_carries_typed_intents():
    plan = make_plan("lookup", secondary_intents=["explanation"])
    assert plan.intent is Intent.LOOKUP
    assert plan.secondary_intents == [Intent.EXPLANATION]


def test_an_unknown_intent_string_passes_through_rather_than_raising():
    """Coercion is best-effort: an unrecognised label stays visible in the plan (and in the
    audit trail) instead of blowing up the run at construction."""
    plan = make_plan("some_new_intent")
    assert plan.intent == "some_new_intent"


def test_a_plan_serializes_intents_to_plain_strings():
    data = make_plan(Intent.RISK_ANALYSIS, secondary_intents=[Intent.LOOKUP]).to_dict()
    assert data["intent"] == "risk_analysis"
    assert data["secondary_intents"] == ["lookup"]
    json.dumps(data)
