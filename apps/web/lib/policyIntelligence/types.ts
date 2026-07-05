/**
 * Policy Intelligence domain types — Policy Hunter's obligations/coverage-gap findings and
 * Policy Analyst's policy-quality findings (PI-P6). These are produced entirely by
 * `apps/api`'s Tool Registry (PI-P5, ADR-0022); this package only shapes the JSON it returns
 * into the frontend's camelCase convention (`lib/policyIntelligence/service.ts` is the one
 * place that translation happens — never re-derived here).
 */

export const SEVERITIES = ["critical", "high", "medium", "low", "informational"] as const;
export type ObligationSeverity = (typeof SEVERITIES)[number];

export interface ObligationEvidence {
  obligationId: string;
  obligationText: string;
  obligationType: string;
  controlDomain: string;
  severity: ObligationSeverity;
  suggestedPolicyTitle: string;
  classificationConfidence: number;
  sourceId: string;
  sourceUrl: string;
  citation: string;
}

export const GAP_CATEGORIES = [
  "unmapped_regulatory_obligation",
  "missing_required_policy",
  "incomplete_coverage",
  "outdated_policy",
] as const;
export type GapCategory = (typeof GAP_CATEGORIES)[number];

export interface GapFinding {
  obligationId: string;
  gapCategory: GapCategory;
  sourceId: string;
  sourceUrl: string;
  citation: string;
  confidence: number;
  matchedPolicyId: string | null;
  matchedPolicyTitle: string | null;
  rationale: string;
}

export interface CoverageGapScan {
  findings: GapFinding[];
  obligationsScanned: number;
  policiesConsidered: number;
}

export const QUALITY_FINDING_TYPES = [
  "missing_required_section",
  "missing_clause",
  "weak_regulatory_coverage",
  "outdated_reference",
  "conflicting_requirements",
  "unclear_ownership",
  "ambiguous_language",
  "stale_policy",
  "policy_older_than_regulation",
] as const;
export type QualityFindingType = (typeof QUALITY_FINDING_TYPES)[number];

export interface QualityFinding {
  findingType: QualityFindingType;
  severity: ObligationSeverity;
  evidence: string;
  citation: string;
  recommendation: string;
  confidence: number;
  relatedObligationId: string | null;
}

export interface PolicyQualityReview {
  policyId: string;
  findings: QualityFinding[];
  obligationsConsidered: number;
}
