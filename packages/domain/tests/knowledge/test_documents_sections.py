"""Unit tests for KnowledgeDocument and KnowledgeSection child entities."""
from __future__ import annotations

import pytest

from grc_domain.knowledge import (
    ContentHash,
    DocumentFormat,
    KnowledgeDocument,
    KnowledgeSection,
    KnowledgeSectionNotFound,
    PageRange,
    SectionType,
    StorageLocator,
    StructuralAnchor,
)
from grc_domain.shared.exceptions import InvariantViolation
from grc_domain.shared.identifiers import (
    KnowledgeDocumentId,
    KnowledgeSectionId,
    KnowledgeSourceVersionId,
)

VER = KnowledgeSourceVersionId("ver-1")
DOC = KnowledgeDocumentId("doc-1")


def make_document() -> KnowledgeDocument:
    return KnowledgeDocument.create(
        id=DOC,
        version_id=VER,
        language="ar",
        document_format=DocumentFormat.PDF,
        storage_locator=StorageLocator("s3://bucket/doc-ar.pdf"),
        content_hash=ContentHash("sha256", "abc"),
    )


def make_section(section_id: str = "sec-1") -> KnowledgeSection:
    return KnowledgeSection.create(
        id=KnowledgeSectionId(section_id),
        document_id=DOC,
        anchor=StructuralAnchor(SectionType.ARTICLE, "5"),
        position=1,
        page_range=PageRange(3, 3),
    )


# --- KnowledgeDocument ---------------------------------------------------------------------
def test_document_create_validation() -> None:
    with pytest.raises(ValueError):
        KnowledgeDocument.create(
            id=DOC,
            version_id=VER,
            language="   ",
            document_format=DocumentFormat.PDF,
            storage_locator=StorageLocator("s3://b/k"),
            content_hash=ContentHash("sha256", "x"),
        )


def test_document_translation_requires_reference() -> None:
    with pytest.raises(ValueError):
        KnowledgeDocument.create(
            id=DOC,
            version_id=VER,
            language="en",
            document_format=DocumentFormat.PDF,
            storage_locator=StorageLocator("s3://b/k"),
            content_hash=ContentHash("sha256", "x"),
            is_translation=True,
        )


def test_document_rejects_negative_counts() -> None:
    with pytest.raises(ValueError):
        KnowledgeDocument.create(
            id=DOC,
            version_id=VER,
            language="en",
            document_format=DocumentFormat.PDF,
            storage_locator=StorageLocator("s3://b/k"),
            content_hash=ContentHash("sha256", "x"),
            page_count=-1,
        )


def test_add_section_and_lookup() -> None:
    doc = make_document()
    section = make_section("sec-1")
    doc.add_section(section)
    assert doc.section(KnowledgeSectionId("sec-1")) is section
    with pytest.raises(KnowledgeSectionNotFound):
        doc.section(KnowledgeSectionId("missing"))


def test_add_section_rejects_foreign_document() -> None:
    doc = make_document()
    foreign = KnowledgeSection.create(
        id=KnowledgeSectionId("sec-x"),
        document_id=KnowledgeDocumentId("other-doc"),
        anchor=StructuralAnchor(SectionType.ARTICLE, "1"),
    )
    with pytest.raises(InvariantViolation):
        doc.add_section(foreign)


def test_add_section_rejects_duplicate() -> None:
    doc = make_document()
    doc.add_section(make_section("sec-1"))
    with pytest.raises(InvariantViolation):
        doc.add_section(make_section("sec-1"))


# --- KnowledgeSection ----------------------------------------------------------------------
def test_section_rejects_negative_position() -> None:
    with pytest.raises(ValueError):
        KnowledgeSection.create(
            id=KnowledgeSectionId("sec-1"),
            document_id=DOC,
            anchor=StructuralAnchor(SectionType.ARTICLE, "5"),
            position=-1,
        )


def test_section_create_defaults() -> None:
    section = KnowledgeSection.create(
        id=KnowledgeSectionId("sec-1"),
        document_id=DOC,
        anchor=StructuralAnchor(SectionType.CLAUSE, "5(2)"),
    )
    assert section.position == 0
    assert section.title is None
    assert section.parent_section_id is None
