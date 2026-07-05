"""Unit tests for the pure, deterministic Policy Analyst quality engine: a complete policy
passes with zero findings, a missing required section, an outdated (stale) policy, weak
regulatory coverage, a missing clause, an outdated reference, a policy older than its linked
regulation, conflicting clauses, unclear ownership, and ambiguous language."""

from __future__ import annotations

from datetime import datetime, timezone

from grc_policy_analyst import FindingType, PolicyDocument, RelatedObligation, review_policy

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)
_RECENT = datetime(2026, 6, 1, tzinfo=timezone.utc)
_OLD_SOURCE = datetime(2026, 1, 1, tzinfo=timezone.utc)

_COMPLETE_BODY = """
Purpose: This policy establishes requirements for access control.
Scope: Applies to all employees and systems.
Ownership: The CISO owns this policy.
Responsibilities: Managers approve access. IT provisions accounts.
Controls: Multi-factor authentication is required for all privileged accounts.
Review cycle: This policy is reviewed annually by the security team.
Exceptions: Exceptions must be approved in writing by the CISO.
""".strip()


def _policy(
    *,
    policy_id: str = "pol-1",
    title: str = "Access Control Policy",
    body: str | None = _COMPLETE_BODY,
    owner_name: str = "CISO",
    updated_at: datetime = _RECENT,
) -> PolicyDocument:
    return PolicyDocument(
        policy_id=policy_id,
        title=title,
        summary="Defines access control requirements.",
        body=body,
        status="published",
        owner_name=owner_name,
        updated_at=updated_at,
    )


def _obligation(
    *,
    obligation_id: str = "ob-1",
    obligation_text: str = (
        "Entities shall implement multi-factor authentication for privileged accounts."
    ),
    suggested_policy_title: str = "Access Control Policy",
    fetched_at: datetime = _OLD_SOURCE,
) -> RelatedObligation:
    return RelatedObligation(
        obligation_id=obligation_id,
        obligation_text=obligation_text,
        suggested_policy_title=suggested_policy_title,
        control_domain="access_control",
        source_id="sa-sama",
        source_url="https://www.sama.gov.sa/circulars/1",
        source_document_fetched_at=fetched_at,
    )


def test_a_complete_well_covered_policy_produces_no_findings() -> None:
    result = review_policy(_policy(), (_obligation(),), now=_NOW)
    assert result.findings == ()
    assert result.obligations_considered == 1


def test_missing_required_section_is_detected() -> None:
    body_without_exceptions = _COMPLETE_BODY.replace(
        "Exceptions: Exceptions must be approved in writing by the CISO.", ""
    )
    result = review_policy(_policy(body=body_without_exceptions), (), now=_NOW)

    missing = [f for f in result.findings if f.finding_type == FindingType.MISSING_REQUIRED_SECTION]
    assert len(missing) == 1
    assert "exceptions" in missing[0].evidence.lower()
    assert missing[0].citation == "policy:pol-1"
    assert missing[0].related_obligation_id is None


def test_policy_with_empty_body_is_missing_every_required_section() -> None:
    result = review_policy(_policy(body=None), (), now=_NOW)
    missing_types = {f.finding_type for f in result.findings}
    assert FindingType.MISSING_REQUIRED_SECTION in missing_types
    missing_count = sum(
        1 for f in result.findings if f.finding_type == FindingType.MISSING_REQUIRED_SECTION
    )
    assert missing_count == 7  # all seven required sections


def test_stale_policy_is_detected() -> None:
    stale_policy = _policy(updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    result = review_policy(stale_policy, (), now=_NOW)

    stale = [f for f in result.findings if f.finding_type == FindingType.STALE_POLICY]
    assert len(stale) == 1
    assert stale[0].citation == "policy:pol-1"


def test_weak_regulatory_coverage_is_detected() -> None:
    weakly_related = _obligation(
        obligation_text=(
            "Entities shall implement strong authentication controls for privileged system "
            "access to prevent unauthorized use."
        )
    )
    result = review_policy(_policy(), (weakly_related,), now=_NOW)

    weak = [f for f in result.findings if f.finding_type == FindingType.WEAK_REGULATORY_COVERAGE]
    assert len(weak) == 1
    assert weak[0].related_obligation_id == "ob-1"
    assert weak[0].citation == "sa-sama#ob-1"


def test_missing_clause_when_relevant_obligation_is_entirely_unaddressed() -> None:
    unaddressed = _obligation(
        obligation_text=(
            "Entities shall log every privileged session to a tamper-evident audit trail."
        )
    )
    result = review_policy(_policy(), (unaddressed,), now=_NOW)

    missing_clause = [f for f in result.findings if f.finding_type == FindingType.MISSING_CLAUSE]
    assert len(missing_clause) == 1
    assert missing_clause[0].related_obligation_id == "ob-1"


def test_unrelated_obligation_produces_no_finding_at_all() -> None:
    """An obligation whose title has nothing to do with this policy is not this policy's
    problem to report (that's Policy Hunter's job) — no false positive here."""
    unrelated = _obligation(
        obligation_text="Entities shall retain financial transaction records for seven years.",
        suggested_policy_title="Financial Records Retention Policy",
    )
    result = review_policy(_policy(), (unrelated,), now=_NOW)
    assert result.findings == ()


def test_policy_older_than_regulation_when_strongly_covered_but_source_is_newer() -> None:
    newer_obligation = _obligation(fetched_at=datetime(2026, 6, 15, tzinfo=timezone.utc))
    result = review_policy(
        _policy(updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc)), (newer_obligation,), now=_NOW
    )

    older = [
        f for f in result.findings if f.finding_type == FindingType.POLICY_OLDER_THAN_REGULATION
    ]
    assert len(older) == 1
    assert older[0].related_obligation_id == "ob-1"


def test_outdated_reference_when_weakly_covered_and_source_is_newer() -> None:
    weakly_related_and_newer = _obligation(
        obligation_text=(
            "Entities shall implement strong authentication controls for privileged system "
            "access to prevent unauthorized use."
        ),
        fetched_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )
    result = review_policy(
        _policy(updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        (weakly_related_and_newer,),
        now=_NOW,
    )

    outdated = [f for f in result.findings if f.finding_type == FindingType.OUTDATED_REFERENCE]
    assert len(outdated) == 1


def test_conflicting_requirements_when_the_same_cadence_anchor_has_two_frequencies() -> None:
    conflicting_body = (
        _COMPLETE_BODY
        + " In addition, this policy shall be reviewed quarterly by the compliance department."
    )
    result = review_policy(_policy(body=conflicting_body), (), now=_NOW)

    conflicts = [
        f for f in result.findings if f.finding_type == FindingType.CONFLICTING_REQUIREMENTS
    ]
    assert len(conflicts) == 1
    assert "annually" in conflicts[0].evidence and "quarterly" in conflicts[0].evidence


def test_no_false_conflict_between_unrelated_uses_of_a_generic_word() -> None:
    """'Access reviews are conducted quarterly' and 'this policy is reviewed annually' must
    not collide just because both loosely relate to 'review' — no false positive."""
    body = _COMPLETE_BODY + " Access reviews are conducted quarterly by the access team."
    result = review_policy(_policy(body=body), (), now=_NOW)
    assert not [
        f for f in result.findings if f.finding_type == FindingType.CONFLICTING_REQUIREMENTS
    ]


def test_unclear_ownership_for_a_placeholder_owner() -> None:
    result = review_policy(_policy(owner_name="TBD"), (), now=_NOW)
    unclear = [f for f in result.findings if f.finding_type == FindingType.UNCLEAR_OWNERSHIP]
    assert len(unclear) == 1
    assert "TBD" in unclear[0].evidence


def test_unclear_ownership_for_an_empty_owner() -> None:
    result = review_policy(_policy(owner_name=""), (), now=_NOW)
    assert any(f.finding_type == FindingType.UNCLEAR_OWNERSHIP for f in result.findings)


def test_ambiguous_language_is_detected() -> None:
    body = _COMPLETE_BODY + " Access shall be reviewed as appropriate."
    result = review_policy(_policy(body=body), (), now=_NOW)

    ambiguous = [f for f in result.findings if f.finding_type == FindingType.AMBIGUOUS_LANGUAGE]
    assert len(ambiguous) == 1
    assert "as appropriate" in ambiguous[0].evidence


def test_every_finding_has_a_recommendation_and_valid_confidence() -> None:
    body = _COMPLETE_BODY + " Access shall be reviewed as appropriate."
    result = review_policy(_policy(body=body, owner_name="TBD"), (), now=_NOW)
    assert result.findings
    for finding in result.findings:
        assert finding.recommendation
        assert 0.0 <= finding.confidence <= 1.0
