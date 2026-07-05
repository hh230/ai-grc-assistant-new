"""Unit tests for the pure, deterministic Policy Hunter matching engine: missing-policy
detection, an existing (covered) match, an outdated policy, incomplete coverage, an unmapped
obligation, and — critically — no false positives on genuinely covered obligations."""

from __future__ import annotations

from datetime import datetime, timezone

from grc_policy_hunter import GapCategory, ObligationSummary, PolicySummary, scan_coverage

_SOURCE_FETCHED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
_POLICY_UPDATED_AFTER_SOURCE = datetime(2026, 2, 1, tzinfo=timezone.utc)
_POLICY_UPDATED_BEFORE_SOURCE = datetime(2025, 6, 1, tzinfo=timezone.utc)


def _obligation(
    *,
    obligation_id: str = "ob-1",
    suggested_policy_title: str = "Access Control Policy",
    obligation_text: str = (
        "Entities shall implement multi-factor authentication for privileged accounts."
    ),
    control_domain: str = "access_control",
    fetched_at: datetime = _SOURCE_FETCHED_AT,
) -> ObligationSummary:
    return ObligationSummary(
        obligation_id=obligation_id,
        obligation_text=obligation_text,
        obligation_type="requirement",
        control_domain=control_domain,
        severity="high",
        suggested_policy_title=suggested_policy_title,
        classification_confidence=0.9,
        source_id="sa-sama",
        source_url="https://www.sama.gov.sa/circulars/1",
        source_document_fetched_at=fetched_at,
    )


def _policy(
    *,
    policy_id: str = "pol-1",
    title: str = "Access Control Policy",
    summary: (
        str | None
    ) = "Defines access control requirements including MFA for privileged accounts.",
    status: str = "published",
    updated_at: datetime = _POLICY_UPDATED_AFTER_SOURCE,
) -> PolicySummary:
    return PolicySummary(
        policy_id=policy_id, title=title, summary=summary, status=status, updated_at=updated_at
    )


def test_missing_required_policy_when_only_a_weak_signal_exists() -> None:
    obligation = _obligation(
        suggested_policy_title="Data Breach Notification",
        obligation_text=(
            "Entities shall notify the regulator of a data breach within 72 hours of discovery."
        ),
    )
    unrelated_policy = _policy(
        title="Data Protection Policy",
        summary="General policy on data protection principles and data subject rights.",
    )

    result = scan_coverage((obligation,), (unrelated_policy,))

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.gap_category == GapCategory.MISSING_REQUIRED_POLICY
    assert finding.matched_policy_id == "pol-1"  # still the closest, if insufficient, match
    assert 0.0 <= finding.confidence <= 1.0


def test_existing_policy_match_produces_no_finding() -> None:
    """No false positive: a policy that substantively covers the obligation, and postdates
    the source regulation, must not be reported as a gap."""
    obligation = _obligation()
    matching_policy = _policy(updated_at=_POLICY_UPDATED_AFTER_SOURCE)

    result = scan_coverage((obligation,), (matching_policy,))

    assert result.findings == ()
    assert result.obligations_scanned == 1
    assert result.policies_considered == 1


def test_outdated_policy_when_source_regulation_is_newer_than_the_matched_policy() -> None:
    obligation = _obligation(fetched_at=_SOURCE_FETCHED_AT)
    stale_policy = _policy(updated_at=_POLICY_UPDATED_BEFORE_SOURCE)

    result = scan_coverage((obligation,), (stale_policy,))

    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.gap_category == GapCategory.OUTDATED_POLICY
    assert finding.matched_policy_id == "pol-1"
    assert finding.matched_policy_title == "Access Control Policy"
    assert finding.confidence > 0.0


def test_incomplete_coverage_for_a_partially_overlapping_policy() -> None:
    obligation = _obligation(
        suggested_policy_title="Data Retention Policy",
        obligation_text="Entities shall retain transaction records for a minimum of five years.",
    )
    generic_policy = _policy(
        title="Data Protection Policy",
        summary=(
            "This policy governs data retention, encryption, and access control for customer "
            "records."
        ),
    )

    result = scan_coverage((obligation,), (generic_policy,))

    assert len(result.findings) == 1
    assert result.findings[0].gap_category == GapCategory.INCOMPLETE_COVERAGE


def test_unmapped_regulatory_obligation_when_nothing_overlaps_at_all() -> None:
    obligation = _obligation(
        suggested_policy_title="Incident Reporting",
        obligation_text=(
            "Entities shall report security incidents to the regulator within 72 hours."
        ),
    )
    unrelated_policy = _policy(
        title="Vendor Management Policy",
        summary="Governs selection and oversight of third-party vendors.",
    )

    result = scan_coverage((obligation,), (unrelated_policy,))

    assert len(result.findings) == 1
    assert result.findings[0].gap_category == GapCategory.UNMAPPED_REGULATORY_OBLIGATION
    assert result.findings[0].matched_policy_id is None
    assert result.findings[0].matched_policy_title is None
    assert result.findings[0].confidence == 1.0  # maximally confident nothing covers it


def test_unmapped_regulatory_obligation_when_tenant_has_no_policies_at_all() -> None:
    obligation = _obligation()

    result = scan_coverage((obligation,), ())

    assert result.policies_considered == 0
    assert len(result.findings) == 1
    assert result.findings[0].gap_category == GapCategory.UNMAPPED_REGULATORY_OBLIGATION


def test_every_finding_carries_full_evidence() -> None:
    obligation = _obligation()
    result = scan_coverage((obligation,), ())

    finding = result.findings[0]
    assert finding.obligation_id == "ob-1"
    assert finding.source_id == "sa-sama"
    assert finding.source_url == "https://www.sama.gov.sa/circulars/1"
    assert finding.citation == "sa-sama#ob-1"
    assert finding.rationale


def test_no_false_positives_across_a_mixed_batch_of_fully_covered_obligations() -> None:
    """A batch where every obligation is genuinely, currently covered must yield zero
    findings — Policy Hunter must not invent gaps for well-covered obligations."""
    obligations = (
        _obligation(obligation_id="ob-1"),
        _obligation(
            obligation_id="ob-2",
            suggested_policy_title="Business Continuity Plan",
            obligation_text="Entities shall maintain a business continuity plan reviewed annually.",
            control_domain="business_continuity",
        ),
    )
    policies = (
        _policy(policy_id="pol-1"),
        _policy(
            policy_id="pol-2",
            title="Business Continuity Policy",
            summary=(
                "This policy requires maintaining a business continuity plan that is "
                "reviewed annually."
            ),
        ),
    )

    result = scan_coverage(obligations, policies)

    assert result.findings == ()
    assert result.obligations_scanned == 2
    assert result.policies_considered == 2


def test_scan_with_no_obligations_returns_an_empty_result() -> None:
    result = scan_coverage((), (_policy(),))
    assert result.findings == ()
    assert result.obligations_scanned == 0
