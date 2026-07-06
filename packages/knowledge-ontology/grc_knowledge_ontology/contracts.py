"""Missing-clause detection — pure, deterministic, no LLM (CLAUDE.md §1: a comparison problem
gets a reproducible algorithm, the same reasoning ADR-0020/0021 used for Policy Hunter/
Analyst's coverage-gap checks). Given a ``ContractType`` and the clause ids a reviewer has
already confirmed are present in an actual contract, reports which of that type's *required*
clauses are absent."""

from __future__ import annotations

from collections.abc import Collection

from .enums import ClauseCategory
from .models import Clause, ContractType


def detect_missing_clauses(
    contract_type: ContractType, present_clause_ids: Collection[str]
) -> tuple[Clause, ...]:
    """The required clauses of ``contract_type`` whose ``clause_id`` is not in
    ``present_clause_ids`` — preserving the contract type's own clause order."""
    present = set(present_clause_ids)
    return tuple(
        clause
        for clause in contract_type.clauses
        if clause.category is ClauseCategory.REQUIRED and clause.clause_id not in present
    )
