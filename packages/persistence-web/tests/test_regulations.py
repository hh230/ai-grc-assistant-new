"""Integration tests for the Saudi Regulations Ingestion persistence layer (KI-P6, ADR-0030)
against apps/web's live `regulation_sources`/`regulation_source_versions`/
`regulation_documents`/`regulation_sections` tables: source create-if-absent, version dedup on
content_hash (unchanged content is a no-op; changed content drafts a new version), pending
review listing, admin approve/reject, and section bulk insert preserving order/hierarchy."""

from __future__ import annotations

import uuid

from grc_persistence_web import (
    Database,
    NewRegulationSection,
    RegulationDocumentRepository,
    RegulationSectionRepository,
    RegulationSourceRepository,
    RegulationSourceVersionRepository,
)


def _unique_short_code() -> str:
    return f"test-reg-{uuid.uuid4()}"


async def _cleanup_source(database: Database, source_id: str) -> None:
    async with database.pool.acquire() as connection:
        await connection.execute(
            """
            DELETE FROM regulation_sections WHERE document_id IN (
              SELECT id FROM regulation_documents WHERE version_id IN (
                SELECT id FROM regulation_source_versions WHERE source_id = $1
              )
            )
            """,
            source_id,
        )
        await connection.execute(
            "DELETE FROM regulation_documents WHERE version_id IN "
            "(SELECT id FROM regulation_source_versions WHERE source_id = $1)",
            source_id,
        )
        await connection.execute(
            "DELETE FROM regulation_source_versions WHERE source_id = $1", source_id
        )
        await connection.execute("DELETE FROM regulation_sources WHERE id = $1", source_id)


async def test_source_upsert_is_create_if_absent(database: Database) -> None:
    short_code = _unique_short_code()
    repository = RegulationSourceRepository(database)
    source_id = str(uuid.uuid4())
    try:
        created = await repository.upsert(
            id=source_id,
            short_code=short_code,
            title_ar="النظام الأساسي للحكم",
            title_en="Basic Law of Governance",
            authority="هيئة الخبراء بمجلس الوزراء",
            jurisdiction="SA",
            knowledge_domain="legal_regulatory",
            document_type="law",
            boe_source_url="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/x/1",
        )
        assert created.title_en == "Basic Law of Governance"

        # A second upsert with a different title must NOT overwrite the existing row.
        again = await repository.upsert(
            id=str(uuid.uuid4()),
            short_code=short_code,
            title_ar="عنوان مختلف",
            authority="a different authority",
            jurisdiction="SA",
            knowledge_domain="legal_regulatory",
            document_type="law",
            boe_source_url="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/x/1",
        )
        assert again.id == created.id
        assert again.title_ar == "النظام الأساسي للحكم"

        fetched = await repository.get_by_short_code(short_code)
        assert fetched is not None
        assert fetched.id == source_id
    finally:
        await _cleanup_source(database, source_id)


async def _make_source(database: Database, short_code: str) -> str:
    source_id = str(uuid.uuid4())
    await RegulationSourceRepository(database).upsert(
        id=source_id,
        short_code=short_code,
        title_ar="نظام تجريبي",
        authority="test authority",
        jurisdiction="SA",
        knowledge_domain="legal_regulatory",
        document_type="law",
        boe_source_url="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/test/1",
    )
    return source_id


async def test_upsert_draft_is_a_noop_when_content_is_unchanged(database: Database) -> None:
    short_code = _unique_short_code()
    source_id = await _make_source(database, short_code)
    repository = RegulationSourceVersionRepository(database)
    try:
        first, created_first = await repository.upsert_draft(
            id=str(uuid.uuid4()),
            source_id=source_id,
            version_label="v1",
            content_hash="hash-v1",
        )
        assert created_first is True
        assert first.status == "in_review"

        replayed, created_again = await repository.upsert_draft(
            id=str(uuid.uuid4()),  # even a different candidate id must not matter
            source_id=source_id,
            version_label="v1",
            content_hash="hash-v1",  # unchanged
        )
        assert created_again is False
        assert replayed.id == first.id
    finally:
        await _cleanup_source(database, source_id)


async def test_upsert_draft_creates_a_new_version_when_content_changes(
    database: Database,
) -> None:
    short_code = _unique_short_code()
    source_id = await _make_source(database, short_code)
    repository = RegulationSourceVersionRepository(database)
    try:
        first, _ = await repository.upsert_draft(
            id=str(uuid.uuid4()),
            source_id=source_id,
            version_label="v1",
            content_hash="hash-v1",
        )
        second, created = await repository.upsert_draft(
            id=str(uuid.uuid4()),
            source_id=source_id,
            version_label="v2",
            content_hash="hash-v2",  # changed
        )
        assert created is True
        assert second.id != first.id

        latest = await repository.get_latest_for_source(source_id)
        assert latest is not None
        assert latest.id == second.id
    finally:
        await _cleanup_source(database, source_id)


async def test_list_pending_and_approve_and_reject(database: Database) -> None:
    short_code = _unique_short_code()
    source_id = await _make_source(database, short_code)
    repository = RegulationSourceVersionRepository(database)
    try:
        version, _ = await repository.upsert_draft(
            id=str(uuid.uuid4()),
            source_id=source_id,
            version_label="v1",
            content_hash="hash-pending",
        )
        pending = await repository.list_pending(limit=200)
        assert any(v.id == version.id for v in pending)

        approved = await repository.approve(version.id, approved_by="admin-1")
        assert approved is not None
        assert approved.status == "approved"
        assert approved.approved_by == "admin-1"
        assert approved.approved_at is not None

        # Already-approved: a second approve/reject call is a no-op (state-checked).
        rejected = await repository.reject(version.id)
        assert rejected is None
    finally:
        await _cleanup_source(database, source_id)


async def test_documents_and_sections_round_trip_preserving_arabic_text_and_order(
    database: Database,
) -> None:
    short_code = _unique_short_code()
    source_id = await _make_source(database, short_code)
    version_repository = RegulationSourceVersionRepository(database)
    document_repository = RegulationDocumentRepository(database)
    section_repository = RegulationSectionRepository(database)
    try:
        version, _ = await version_repository.upsert_draft(
            id=str(uuid.uuid4()),
            source_id=source_id,
            version_label="v1",
            content_hash="hash-sections",
        )
        document = await document_repository.insert(
            id=str(uuid.uuid4()),
            version_id=version.id,
            language="ar",
            document_format="html",
            source_url="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/test/1",
            content_hash="doc-hash-1",
            byte_size=1024,
        )
        documents = await document_repository.list_for_version(version.id)
        assert [d.id for d in documents] == [document.id]

        chapter_id = str(uuid.uuid4())
        article_one_id = str(uuid.uuid4())
        article_two_id = str(uuid.uuid4())
        inserted = await section_repository.bulk_insert(
            (
                NewRegulationSection(
                    id=chapter_id,
                    document_id=document.id,
                    section_type="chapter",
                    code="الباب الأول",
                    path=(),
                    position=0,
                    title_ar="الباب الأول: المبادئ العامة",
                ),
                NewRegulationSection(
                    id=article_one_id,
                    document_id=document.id,
                    section_type="article",
                    code="المادة الأولى",
                    path=("الباب الأول",),
                    position=1,
                    parent_section_id=chapter_id,
                    text_ar="المملكة العربية السعودية، دولة عربية إسلامية.",
                ),
                NewRegulationSection(
                    id=article_two_id,
                    document_id=document.id,
                    section_type="article",
                    code="المادة الثانية",
                    path=("الباب الأول",),
                    position=2,
                    parent_section_id=chapter_id,
                    text_ar="عيدا الدولة، هما عيدا الفطر والأضحى.",
                    amendment_note_ar="عدلت هذه المادة بموجب أمر ملكي.",
                ),
            )
        )
        assert len(inserted) == 3

        sections = await section_repository.list_for_document(document.id)
        assert [s.id for s in sections] == [chapter_id, article_one_id, article_two_id]

        article_one = next(s for s in sections if s.id == article_one_id)
        assert article_one.text_ar == "المملكة العربية السعودية، دولة عربية إسلامية."
        assert article_one.parent_section_id == chapter_id
        assert article_one.path == ["الباب الأول"]

        article_two = next(s for s in sections if s.id == article_two_id)
        assert article_two.amendment_note_ar == "عدلت هذه المادة بموجب أمر ملكي."
    finally:
        await _cleanup_source(database, source_id)


async def test_list_needing_embedding_and_set_embedding(database: Database) -> None:
    """KI-P7 (ADR-0031): only real-text sections (never bare chapter headings) are candidates,
    and a section already embedded drops out of the candidate list — the idempotency an
    approval retry after a partial failure depends on."""
    short_code = _unique_short_code()
    source_id = await _make_source(database, short_code)
    version_repository = RegulationSourceVersionRepository(database)
    document_repository = RegulationDocumentRepository(database)
    section_repository = RegulationSectionRepository(database)
    try:
        version, _ = await version_repository.upsert_draft(
            id=str(uuid.uuid4()),
            source_id=source_id,
            version_label="v1",
            content_hash="hash-embeddings",
        )
        document = await document_repository.insert(
            id=str(uuid.uuid4()),
            version_id=version.id,
            language="ar",
            document_format="html",
            source_url="https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/test/1",
            content_hash="doc-hash-embeddings",
        )
        chapter_id = str(uuid.uuid4())
        article_id = str(uuid.uuid4())
        await section_repository.bulk_insert(
            (
                NewRegulationSection(
                    id=chapter_id,
                    document_id=document.id,
                    section_type="chapter",
                    code="الباب الأول",
                    path=(),
                    position=0,
                    title_ar="الباب الأول",
                ),
                NewRegulationSection(
                    id=article_id,
                    document_id=document.id,
                    section_type="article",
                    code="المادة الأولى",
                    path=("الباب الأول",),
                    position=1,
                    parent_section_id=chapter_id,
                    text_ar="نص المادة الأولى.",
                ),
            )
        )

        candidates = await section_repository.list_needing_embedding(document.id)
        assert [c.id for c in candidates] == [article_id]
        assert candidates[0].text_ar == "نص المادة الأولى."

        # regulation_sections.embedding is vector(3072)
        fake_vector = tuple(0.1 for _ in range(3072))
        await section_repository.set_embedding(
            article_id, embedding=fake_vector, model="text-embedding-3-large"
        )

        # Already embedded: drops out of the candidate list (idempotent retry).
        remaining = await section_repository.list_needing_embedding(document.id)
        assert remaining == []
    finally:
        await _cleanup_source(database, source_id)
