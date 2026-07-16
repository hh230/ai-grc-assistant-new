"""Tenant isolation (ADR 0040 §2): a tenant sees GLOBAL ∪ its own ORGANIZATION data, and never
another tenant's. Enforcement lives inside the corpus filter (the store predicate) and is
re-verified at the engine boundary."""

from __future__ import annotations

from dataclasses import replace

import pytest
from pipeline_contracts import Filter, KnowledgeScope, RetrievalScope, TenancyError
from retrieval_engine import RetrievalEngine
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.interfaces import ScoredHit

from tests.conftest import make_chunk


def _org(chunk_id: str, text: str, org: str):
    return replace(
        make_chunk(chunk_id, text),
        scope_kind=KnowledgeScope.ORGANIZATION,
        organization_id=org,
    )


_CORPUS = InMemoryCorpus.from_chunks(
    [
        make_chunk("g1", "shared framework: access control"),      # GLOBAL (default)
        _org("a1", "org A private access-control policy", "org_acme"),
        _org("b1", "org B private access-control policy", "org_globex"),
    ]
)


def _ids(chunks) -> set[str]:
    return {c.chunk_id for c in chunks}


def test_tenant_sees_global_plus_its_own_organization_only():
    got = _CORPUS.filter(Filter(scope=RetrievalScope.for_tenant("org_acme")))
    assert _ids(got) == {"g1", "a1"}          # global + A, never B


def test_the_other_tenant_is_isolated():
    got = _CORPUS.filter(Filter(scope=RetrievalScope.for_tenant("org_globex")))
    assert _ids(got) == {"g1", "b1"}          # global + B, never A


def test_global_scope_sees_only_global():
    assert _ids(_CORPUS.filter(Filter(scope=RetrievalScope.global_only()))) == {"g1"}


def test_a_scopeless_filter_is_fail_safe_global_only():
    # A filter with no scope must never leak organization data — global only.
    assert _ids(_CORPUS.filter(Filter())) == {"g1"}


class _LeakyVector:
    """A misbehaving provider that ignores the scope and returns an out-of-scope chunk — to
    prove the engine's boundary re-verification catches a scoping bug (ADR 0040 §4)."""

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        leaked = _org("b1", "org B private", "org_globex")
        return [ScoredHit(chunk=leaked, score=1.0, source="vector")]


class _EmptyKeyword:
    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        return []


def test_engine_boundary_refuses_an_out_of_scope_leak():
    from retrieval_engine.planner import RetrievalQuery

    engine = RetrievalEngine(_LeakyVector(), _EmptyKeyword())
    query = RetrievalQuery(
        text="access control", filter=Filter(scope=RetrievalScope.for_tenant("org_acme"))
    )
    with pytest.raises(TenancyError):
        engine.retrieve(query)          # tenant A must never receive tenant B's chunk
