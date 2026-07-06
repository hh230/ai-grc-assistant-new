"""Unit tests for ``detect_missing_clauses``: pure, deterministic comparison of a contract
type's required clauses against the clause ids a reviewer confirms are present."""

from __future__ import annotations

from grc_knowledge_ontology import ClauseCategory, ContractType, detect_missing_clauses
from grc_knowledge_ontology.models import Clause

_REQUIRED_A = Clause(
    clause_id="required_a", name="Required A", category=ClauseCategory.REQUIRED, description="d"
)
_REQUIRED_B = Clause(
    clause_id="required_b", name="Required B", category=ClauseCategory.REQUIRED, description="d"
)
_RISK_CLAUSE = Clause(
    clause_id="risk_a", name="Risk A", category=ClauseCategory.RISK, description="d"
)

_CONTRACT_TYPE = ContractType(
    contract_type_id="test_type",
    name="test contract",
    description="d",
    clauses=(_REQUIRED_A, _REQUIRED_B, _RISK_CLAUSE),
)


def test_detect_missing_clauses_reports_absent_required_clauses() -> None:
    missing = detect_missing_clauses(_CONTRACT_TYPE, present_clause_ids={"required_a"})

    assert missing == (_REQUIRED_B,)


def test_detect_missing_clauses_reports_nothing_when_all_required_clauses_are_present() -> None:
    missing = detect_missing_clauses(
        _CONTRACT_TYPE, present_clause_ids={"required_a", "required_b"}
    )

    assert missing == ()


def test_detect_missing_clauses_ignores_non_required_clauses() -> None:
    """A missing risk/protective clause is not reported — only required clauses are mandatory
    for a contract of this type to be considered complete."""
    missing = detect_missing_clauses(
        _CONTRACT_TYPE, present_clause_ids={"required_a", "required_b"}
    )

    assert _RISK_CLAUSE not in missing


def test_detect_missing_clauses_reports_all_required_clauses_when_none_are_present() -> None:
    missing = detect_missing_clauses(_CONTRACT_TYPE, present_clause_ids=())

    assert missing == (_REQUIRED_A, _REQUIRED_B)
