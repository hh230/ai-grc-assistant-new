"""Unit tests for Knowledge value objects: validation and behavior."""
from __future__ import annotations

import pytest
from grc_domain.knowledge import (
    ContentHash,
    DefinitionPayload,
    KnowledgeObjectType,
    KnowledgeScope,
    KnowledgeScopeKind,
    LocalizedText,
    PageRange,
    ProvenanceRecord,
    RelationshipEndpoint,
    RelationshipEndpointKind,
    RequirementPayload,
    SectionType,
    StorageLocator,
    StructuralAnchor,
    TextSpan,
)
from grc_domain.shared.identifiers import (
    FrameworkControlId,
    FrameworkId,
    KnowledgeObjectId,
    KnowledgeSectionId,
    KnowledgeSourceVersionId,
    OrganizationId,
)


# --- KnowledgeScope ------------------------------------------------------------------------
def test_global_scope_carries_no_tenant() -> None:
    scope = KnowledgeScope.global_()
    assert scope.is_global
    assert not scope.is_organization
    assert scope.organization_id is None


def test_organization_scope_carries_tenant() -> None:
    org = OrganizationId("org-1")
    scope = KnowledgeScope.for_organization(org)
    assert scope.is_organization
    assert scope.organization_id == org


def test_organization_scope_without_org_is_rejected() -> None:
    with pytest.raises(ValueError):
        KnowledgeScope(KnowledgeScopeKind.ORGANIZATION, None)


def test_global_scope_with_org_is_rejected() -> None:
    with pytest.raises(ValueError):
        KnowledgeScope(KnowledgeScopeKind.GLOBAL, OrganizationId("org-1"))


# --- LocalizedText -------------------------------------------------------------------------
def test_localized_text_get_default_languages() -> None:
    text = LocalizedText.from_mapping({"ar": "نظام", "en": "Law"})
    assert text.get("ar") == "نظام"
    assert text.get("en") == "Law"
    assert text.get("fr") is None
    assert text.default == "نظام"  # first entry is the default
    assert text.languages == ("ar", "en")


def test_localized_text_requires_at_least_one_entry() -> None:
    with pytest.raises(ValueError):
        LocalizedText(())


def test_localized_text_rejects_duplicate_language() -> None:
    with pytest.raises(ValueError):
        LocalizedText((("en", "A"), ("en", "B")))


def test_localized_text_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        LocalizedText.of("en", "   ")


# --- StructuralAnchor ----------------------------------------------------------------------
def test_structural_anchor_str_with_and_without_path() -> None:
    bare = StructuralAnchor(SectionType.ARTICLE, "5")
    assert str(bare) == "5"
    nested = StructuralAnchor(SectionType.CLAUSE, "5(2)", path=("Part I", "Chapter 2"))
    assert str(nested) == "Part I/Chapter 2/5(2)"


def test_structural_anchor_rejects_blank_code() -> None:
    with pytest.raises(ValueError):
        StructuralAnchor(SectionType.ARTICLE, "  ")


# --- PageRange / TextSpan ------------------------------------------------------------------
def test_page_range_valid_and_invalid() -> None:
    assert PageRange(1, 3).end_page == 3
    with pytest.raises(ValueError):
        PageRange(0, 3)
    with pytest.raises(ValueError):
        PageRange(5, 2)


def test_text_span_length_and_validation() -> None:
    assert TextSpan(10, 25).length == 15
    with pytest.raises(ValueError):
        TextSpan(-1, 5)
    with pytest.raises(ValueError):
        TextSpan(7, 3)


# --- ContentHash / StorageLocator ----------------------------------------------------------
def test_content_hash_and_storage_locator_require_values() -> None:
    assert ContentHash("sha256", "deadbeef").algorithm == "sha256"
    with pytest.raises(ValueError):
        ContentHash("", "x")
    with pytest.raises(ValueError):
        ContentHash("sha256", " ")
    assert StorageLocator("s3://b/k").uri == "s3://b/k"
    with pytest.raises(ValueError):
        StorageLocator("   ")


# --- ProvenanceRecord ----------------------------------------------------------------------
def test_provenance_minimum_is_source_version() -> None:
    prov = ProvenanceRecord(source_version_id=KnowledgeSourceVersionId("ver-1"))
    assert prov.source_version_id == KnowledgeSourceVersionId("ver-1")


def test_provenance_rejects_blank_extractor_name() -> None:
    with pytest.raises(ValueError):
        ProvenanceRecord(
            source_version_id=KnowledgeSourceVersionId("ver-1"), extractor_name="  "
        )


# --- RelationshipEndpoint ------------------------------------------------------------------
def test_endpoint_for_object_section_and_framework_control() -> None:
    obj = RelationshipEndpoint.for_object(KnowledgeObjectId("obj-1"))
    assert obj.kind is RelationshipEndpointKind.KNOWLEDGE_OBJECT

    sec = RelationshipEndpoint.for_section(KnowledgeSectionId("sec-1"))
    assert sec.kind is RelationshipEndpointKind.SECTION

    fc = RelationshipEndpoint.for_framework_control(
        FrameworkId("framework:iso_27001"), FrameworkControlId("A.8.1")
    )
    assert fc.kind is RelationshipEndpointKind.FRAMEWORK_CONTROL
    assert fc.framework_id == FrameworkId("framework:iso_27001")


def test_endpoint_rejects_mismatched_fields() -> None:
    with pytest.raises(ValueError):
        RelationshipEndpoint(RelationshipEndpointKind.KNOWLEDGE_OBJECT)  # missing object id
    with pytest.raises(ValueError):
        RelationshipEndpoint(
            RelationshipEndpointKind.SECTION,
            section_id=KnowledgeSectionId("sec-1"),
            framework_id=FrameworkId("f"),  # extraneous
        )
    with pytest.raises(ValueError):
        RelationshipEndpoint(
            RelationshipEndpointKind.FRAMEWORK_CONTROL,
            framework_id=FrameworkId("f"),  # control id missing
        )


def test_endpoint_value_equality() -> None:
    a = RelationshipEndpoint.for_object(KnowledgeObjectId("obj-1"))
    b = RelationshipEndpoint.for_object(KnowledgeObjectId("obj-1"))
    c = RelationshipEndpoint.for_object(KnowledgeObjectId("obj-2"))
    assert a == b
    assert a != c


# --- payloads ------------------------------------------------------------------------------
def test_payload_declares_object_type() -> None:
    assert DefinitionPayload.OBJECT_TYPE is KnowledgeObjectType.DEFINITION
    assert RequirementPayload.OBJECT_TYPE is KnowledgeObjectType.REQUIREMENT


def test_definition_payload_requires_term() -> None:
    assert DefinitionPayload(term="Personal Data").term == "Personal Data"
    with pytest.raises(ValueError):
        DefinitionPayload(term="  ")
