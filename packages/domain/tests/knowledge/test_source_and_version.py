"""Unit tests for KnowledgeSource and the KnowledgeSourceVersion governance lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from grc_domain.knowledge import (
    ContentHash,
    DocumentFormat,
    DocumentType,
    KnowledgeDocument,
    KnowledgeDocumentNotFound,
    KnowledgeDomain,
    KnowledgeScope,
    KnowledgeSource,
    KnowledgeSourceVersion,
    LocalizedText,
    PublishRequiresApproval,
    StorageLocator,
    VersionImmutable,
    VersionRequiresDocument,
    VersionStatus,
)
from grc_domain.knowledge.events import (
    KnowledgeSourceRegistered,
    KnowledgeSourceVersionApproved,
    KnowledgeSourceVersionDrafted,
    KnowledgeSourceVersionPublished,
    KnowledgeSourceVersionSuperseded,
)
from grc_domain.knowledge.exceptions import IllegalVersionTransition
from grc_domain.shared.enums import DataClassification
from grc_domain.shared.identifiers import (
    FrameworkId,
    KnowledgeDocumentId,
    KnowledgeSourceId,
    KnowledgeSourceVersionId,
)
from grc_domain.shared.value_objects import Actor, ActorKind

SRC = KnowledgeSourceId("src-1")
VER = KnowledgeSourceVersionId("ver-1")
APPROVER = Actor(kind=ActorKind.USER, reference="curator-1")
T2023 = datetime(2023, 1, 1, tzinfo=timezone.utc)
T2022 = datetime(2022, 1, 1, tzinfo=timezone.utc)
T2024 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def make_source(scope: KnowledgeScope | None = None) -> KnowledgeSource:
    return KnowledgeSource.register(
        id=SRC,
        scope=scope or KnowledgeScope.global_(),
        short_code="PDPL",
        title=LocalizedText.of("en", "Personal Data Protection Law"),
        authority="NCA",
        jurisdiction="SA",
        knowledge_domain=KnowledgeDomain.LEGAL_REGULATORY,
        document_type=DocumentType.LAW,
    )


def make_version(scope: KnowledgeScope | None = None) -> KnowledgeSourceVersion:
    return KnowledgeSourceVersion.draft(
        id=VER,
        source_id=SRC,
        scope=scope or KnowledgeScope.global_(),
        version_label="2023",
    )


def make_document(doc_id: str = "doc-1") -> KnowledgeDocument:
    return KnowledgeDocument.create(
        id=KnowledgeDocumentId(doc_id),
        version_id=VER,
        language="en",
        document_format=DocumentFormat.PDF,
        storage_locator=StorageLocator("s3://bucket/doc.pdf"),
        content_hash=ContentHash("sha256", "abc123"),
    )


# --- KnowledgeSource -----------------------------------------------------------------------
def test_register_sets_fields_and_records_event() -> None:
    source = make_source()
    assert source.short_code == "PDPL"
    assert source.classification is DataClassification.CONFIDENTIAL
    events = source.pull_events()
    assert any(isinstance(e, KnowledgeSourceRegistered) for e in events)
    assert source.pending_events == ()  # pull cleared them


def test_register_trims_and_validates_required_fields() -> None:
    with pytest.raises(ValueError):
        KnowledgeSource.register(
            id=SRC,
            scope=KnowledgeScope.global_(),
            short_code="   ",
            title=LocalizedText.of("en", "X"),
            authority="NCA",
            jurisdiction="SA",
            knowledge_domain=KnowledgeDomain.LEGAL_REGULATORY,
            document_type=DocumentType.LAW,
        )


def test_facet_mutators_dedupe_and_touch() -> None:
    source = make_source()
    fw = FrameworkId("framework:iso_27001")
    source.add_framework_ref(fw)
    source.add_framework_ref(fw)  # idempotent
    assert source.framework_refs == (fw,)
    source.add_tag("privacy")
    source.add_tag(" privacy ")  # trimmed + deduped
    assert source.tags == ("privacy",)


def test_set_current_version_records_event() -> None:
    source = make_source()
    source.set_current_version(VER)
    assert source.current_version_id == VER
    event_names = {e.__class__.__name__ for e in source.pull_events()}
    assert "KnowledgeSourceCurrentVersionSet" in event_names


# --- KnowledgeSourceVersion: happy path ----------------------------------------------------
def test_draft_starts_in_draft_with_event() -> None:
    version = make_version()
    assert version.status is VersionStatus.DRAFT
    assert any(isinstance(e, KnowledgeSourceVersionDrafted) for e in version.pending_events)


def test_full_publish_path() -> None:
    version = make_version()
    version.attach_document(make_document())
    version.submit_for_review()
    version.approve(approver=APPROVER)
    assert version.status is VersionStatus.APPROVED
    assert version.approval is not None and version.approval.actor == APPROVER

    version.publish(effective_from=T2023)
    assert version.status is VersionStatus.PUBLISHED
    assert version.publication_date is not None
    assert version.effective_range is not None and version.effective_range.start == T2023
    assert version.applies_at(T2024) is True
    assert version.applies_at(T2022) is False  # before it came into force

    types = {type(e) for e in version.pending_events}
    assert KnowledgeSourceVersionApproved in types
    assert KnowledgeSourceVersionPublished in types


def test_publish_requires_approval() -> None:
    version = make_version()
    version.attach_document(make_document())
    with pytest.raises(PublishRequiresApproval):
        version.publish(effective_from=T2023)


def test_publish_requires_at_least_one_document() -> None:
    version = make_version()
    version.submit_for_review()
    version.approve(approver=APPROVER)
    with pytest.raises(VersionRequiresDocument):
        version.publish(effective_from=T2023)


def test_content_is_immutable_after_publish() -> None:
    version = make_version()
    version.attach_document(make_document("doc-1"))
    version.submit_for_review()
    version.approve(approver=APPROVER)
    version.publish(effective_from=T2023)
    assert version.is_content_mutable is False
    with pytest.raises(VersionImmutable):
        version.attach_document(make_document("doc-2"))


# --- KnowledgeSourceVersion: transitions ---------------------------------------------------
def test_illegal_transition_draft_to_approved() -> None:
    version = make_version()
    with pytest.raises(IllegalVersionTransition):
        version.approve(approver=APPROVER)  # cannot approve straight from DRAFT


def test_supersede_closes_window_and_blocks_applicability() -> None:
    version = make_version()
    version.attach_document(make_document())
    version.submit_for_review()
    version.approve(approver=APPROVER)
    version.publish(effective_from=T2023)
    successor = KnowledgeSourceVersionId("ver-2")

    version.supersede(superseded_by_version_id=successor)
    assert version.status is VersionStatus.SUPERSEDED
    assert version.superseded_by_version_id == successor
    assert version.effective_range is not None and version.effective_range.end is not None
    assert version.applies_at(T2024) is False  # no longer the in-force version
    assert any(isinstance(e, KnowledgeSourceVersionSuperseded) for e in version.pending_events)


def test_withdraw_then_archive() -> None:
    version = make_version()
    version.attach_document(make_document())
    version.submit_for_review()
    version.approve(approver=APPROVER)
    version.publish(effective_from=T2023)
    version.withdraw(reason="repealed")
    assert version.status is VersionStatus.WITHDRAWN
    version.archive()
    assert version.status is VersionStatus.ARCHIVED


def test_withdraw_requires_reason() -> None:
    version = make_version()
    version.attach_document(make_document())
    version.submit_for_review()
    version.approve(approver=APPROVER)
    version.publish(effective_from=T2023)
    with pytest.raises(ValueError):
        version.withdraw(reason="  ")


def test_reject_from_review() -> None:
    version = make_version()
    version.submit_for_review()
    version.reject(reason="bad import")
    assert version.status is VersionStatus.REJECTED


def test_document_lookup_not_found() -> None:
    version = make_version()
    version.attach_document(make_document("doc-1"))
    assert version.document(KnowledgeDocumentId("doc-1")).id == KnowledgeDocumentId("doc-1")
    with pytest.raises(KnowledgeDocumentNotFound):
        version.document(KnowledgeDocumentId("missing"))
