"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchCoverageGaps,
  fetchObligations,
  fetchPolicyQualityReview,
} from "@/lib/policyIntelligence/client";
import type { CoverageGapScan, ObligationEvidence, PolicyQualityReview } from "@/lib/policyIntelligence/types";

export function useObligations(controlDomain?: string) {
  return useQuery<ObligationEvidence[]>({
    queryKey: ["policy-intelligence", "obligations", controlDomain ?? null],
    queryFn: () => fetchObligations(controlDomain),
  });
}

export function useCoverageGaps(controlDomain?: string) {
  return useQuery<CoverageGapScan>({
    queryKey: ["policy-intelligence", "coverage-gaps", controlDomain ?? null],
    queryFn: () => fetchCoverageGaps(controlDomain),
  });
}

export function usePolicyQualityReview(policyId: string | null) {
  return useQuery<PolicyQualityReview>({
    queryKey: ["policy-intelligence", "quality-review", policyId],
    queryFn: () => fetchPolicyQualityReview(policyId as string),
    enabled: Boolean(policyId),
  });
}
