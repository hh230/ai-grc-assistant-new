"""Integration tests for KnowledgeItemRepository against apps/web's live `knowledge_items`
table: idempotent upsert (unchanged content is a no-op that preserves verification), a real
content change bumping version and resetting to discovered, status transitions, and lookups."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from grc_persistence_web import Database, KnowledgeItemRepository


def _unique_question_id() -> str:
    return f"test.{uuid.uuid4()}"


async def _cleanup(database: Database, question_id: str) -> None:
    async with database.pool.acquire() as connection:
        await connection.execute("DELETE FROM knowledge_items WHERE question_id = $1", question_id)


async def test_upsert_creates_a_discovered_item(database: Database) -> None:
    question_id = _unique_question_id()
    repository = KnowledgeItemRepository(database)
    try:
        created = await repository.upsert(
            id=str(uuid.uuid4()),
            question_id=question_id,
            question="What clauses should exist in a vendor contract?",
            answer="Vendor contracts should include audit rights and exit clauses.",
            domain="vendor_management",
            category="contract_requirements",
            applicable_context="Any vendor contract involving data processing.",
            source_id="sa-sama",
            source_name="Saudi Central Bank (SAMA)",
            source_type="government_regulator",
            source_url="https://www.sama.gov.sa",
            jurisdiction="SA",
            citation="sa-sama#" + question_id,
            confidence=0.85,
            version_hash="hash-v1",
        )

        assert created.status == "discovered"
        assert created.last_verified is None
        assert created.verified_by is None
        assert created.version == 1

        fetched = await repository.get_by_question_id(question_id)
        assert fetched is not None
        assert fetched.id == created.id
    finally:
        await _cleanup(database, question_id)


async def test_upsert_with_unchanged_version_hash_is_a_no_op(database: Database) -> None:
    """Re-running discovery over an unchanged source excerpt must never reset an
    already-verified item's status (ADR-0025)."""
    question_id = _unique_question_id()
    repository = KnowledgeItemRepository(database)
    try:
        await repository.upsert(
            id=str(uuid.uuid4()),
            question_id=question_id,
            question="What clauses should exist in a vendor contract?",
            answer="Vendor contracts should include audit rights and exit clauses.",
            domain="vendor_management",
            category="contract_requirements",
            applicable_context="Any vendor contract involving data processing.",
            source_id="sa-sama",
            source_name="Saudi Central Bank (SAMA)",
            source_type="government_regulator",
            source_url="https://www.sama.gov.sa",
            jurisdiction="SA",
            citation="sa-sama#" + question_id,
            confidence=0.85,
            version_hash="hash-v1",
        )
        verified = await repository.set_verification_status(
            question_id,
            status="verified",
            verified_by="user-compliance",
            verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert verified is not None
        assert verified.status == "verified"

        replayed = await repository.upsert(
            id=str(uuid.uuid4()),  # even a different candidate id must not matter
            question_id=question_id,
            question="What clauses should exist in a vendor contract?",
            answer="Vendor contracts should include audit rights and exit clauses.",
            domain="vendor_management",
            category="contract_requirements",
            applicable_context="Any vendor contract involving data processing.",
            source_id="sa-sama",
            source_name="Saudi Central Bank (SAMA)",
            source_type="government_regulator",
            source_url="https://www.sama.gov.sa",
            jurisdiction="SA",
            citation="sa-sama#" + question_id,
            confidence=0.85,
            version_hash="hash-v1",  # unchanged
        )

        assert replayed.status == "verified"  # untouched
        assert replayed.version == 1  # not bumped
        assert replayed.last_verified is not None
    finally:
        await _cleanup(database, question_id)


async def test_upsert_with_changed_version_hash_bumps_version_and_resets_status(
    database: Database,
) -> None:
    question_id = _unique_question_id()
    repository = KnowledgeItemRepository(database)
    try:
        await repository.upsert(
            id=str(uuid.uuid4()),
            question_id=question_id,
            question="What clauses should exist in a vendor contract?",
            answer="Vendor contracts should include audit rights and exit clauses.",
            domain="vendor_management",
            category="contract_requirements",
            applicable_context="Any vendor contract involving data processing.",
            source_id="sa-sama",
            source_name="Saudi Central Bank (SAMA)",
            source_type="government_regulator",
            source_url="https://www.sama.gov.sa",
            jurisdiction="SA",
            citation="sa-sama#" + question_id,
            confidence=0.85,
            version_hash="hash-v1",
        )
        await repository.set_verification_status(
            question_id,
            status="verified",
            verified_by="user-compliance",
            verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        updated = await repository.upsert(
            id=str(uuid.uuid4()),
            question_id=question_id,
            question="What clauses should exist in a vendor contract?",
            answer="Vendor contracts should also include a data breach notification clause.",
            domain="vendor_management",
            category="contract_requirements",
            applicable_context="Any vendor contract involving data processing.",
            source_id="sa-sama",
            source_name="Saudi Central Bank (SAMA)",
            source_type="government_regulator",
            source_url="https://www.sama.gov.sa",
            jurisdiction="SA",
            citation="sa-sama#" + question_id,
            confidence=0.6,
            version_hash="hash-v2",  # changed
        )

        assert updated.version == 2
        assert updated.status == "discovered"  # reset — needs human attention again
        assert updated.last_verified is None
        assert updated.verified_by is None
        assert "breach notification" in updated.answer
    finally:
        await _cleanup(database, question_id)


async def test_upsert_accepts_needs_review_status_with_no_last_verified(
    database: Database,
) -> None:
    """KI-P5 follow-up: a below-confidence-threshold discovery is stored as 'needs_review',
    not discarded — and, unlike 'verified'/'outdated', this status legitimately carries no
    last_verified timestamp (nobody has looked at it yet)."""
    question_id = _unique_question_id()
    repository = KnowledgeItemRepository(database)
    try:
        created = await repository.upsert(
            id=str(uuid.uuid4()),
            question_id=question_id,
            question="What clauses should exist in a vendor contract?",
            answer="Vendor contracts should probably include audit rights.",
            domain="vendor_management",
            category="contract_requirements",
            applicable_context="Any vendor contract involving data processing.",
            source_id="sa-sama",
            source_name="Saudi Central Bank (SAMA)",
            source_type="government_regulator",
            source_url="https://www.sama.gov.sa",
            jurisdiction="SA",
            citation="sa-sama#" + question_id,
            confidence=0.3,
            version_hash="hash-v1",
            status="needs_review",
        )

        assert created.status == "needs_review"
        assert created.last_verified is None
    finally:
        await _cleanup(database, question_id)


async def test_list_by_status_and_list_all(database: Database) -> None:
    question_id = _unique_question_id()
    repository = KnowledgeItemRepository(database)
    try:
        await repository.upsert(
            id=str(uuid.uuid4()),
            question_id=question_id,
            question="What clauses should exist in a vendor contract?",
            answer="Vendor contracts should include audit rights and exit clauses.",
            domain="vendor_management",
            category="contract_requirements",
            applicable_context="Any vendor contract involving data processing.",
            source_id="sa-sama",
            source_name="Saudi Central Bank (SAMA)",
            source_type="government_regulator",
            source_url="https://www.sama.gov.sa",
            jurisdiction="SA",
            citation="sa-sama#" + question_id,
            confidence=0.85,
            version_hash="hash-v1",
        )

        discovered = await repository.list_by_status("discovered")
        assert any(item.question_id == question_id for item in discovered)

        all_items = await repository.list_all()
        assert any(item.question_id == question_id for item in all_items)

        verified = await repository.list_by_status("verified")
        assert all(item.question_id != question_id for item in verified)
    finally:
        await _cleanup(database, question_id)


async def test_get_returns_none_for_unknown_item(database: Database) -> None:
    repository = KnowledgeItemRepository(database)
    assert await repository.get(str(uuid.uuid4())) is None
    assert await repository.get_by_question_id(_unique_question_id()) is None


async def test_set_verification_status_returns_none_for_unknown_question(
    database: Database,
) -> None:
    repository = KnowledgeItemRepository(database)
    result = await repository.set_verification_status(
        _unique_question_id(),
        status="verified",
        verified_by="user-compliance",
        verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert result is None
