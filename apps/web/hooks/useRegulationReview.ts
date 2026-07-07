"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  approveRegulationVersion,
  fetchPendingRegulationVersions,
  fetchRegulationVersionDetail,
  rejectRegulationVersion,
} from "@/lib/regulationReview/client";
import type {
  ApproveRegulationResult,
  PendingRegulationVersion,
  RegulationVersionDetail,
  RejectRegulationResult,
} from "@/lib/regulationReview/types";

const QUERY_KEY_ROOT = "regulation-review";

export function usePendingRegulationVersions() {
  return useQuery<PendingRegulationVersion[]>({
    queryKey: [QUERY_KEY_ROOT, "pending"],
    queryFn: fetchPendingRegulationVersions,
  });
}

export function useRegulationVersionDetail(versionId: string | null) {
  return useQuery<RegulationVersionDetail>({
    queryKey: [QUERY_KEY_ROOT, "detail", versionId],
    queryFn: () => fetchRegulationVersionDetail(versionId as string),
    enabled: versionId !== null,
  });
}

function useInvalidateRegulationReviewQueries() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: [QUERY_KEY_ROOT] });
}

export function useApproveRegulationVersion() {
  const invalidate = useInvalidateRegulationReviewQueries();
  return useMutation<ApproveRegulationResult, Error, string>({
    mutationFn: (versionId: string) => approveRegulationVersion(versionId),
    onSuccess: () => invalidate(),
  });
}

export function useRejectRegulationVersion() {
  const invalidate = useInvalidateRegulationReviewQueries();
  return useMutation<RejectRegulationResult, Error, string>({
    mutationFn: (versionId: string) => rejectRegulationVersion(versionId),
    onSuccess: () => invalidate(),
  });
}
