"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createPolicy,
  deletePolicy,
  fetchPolicies,
  fetchPolicy,
  transitionPolicy,
  updatePolicy,
  type PolicyInput,
} from "@/lib/policies/client";
import type { Policy, PolicyStatus, PolicySummary } from "@/lib/policies/types";

const POLICIES_KEY = ["policies"] as const;

export function usePolicies() {
  return useQuery<PolicySummary[]>({ queryKey: POLICIES_KEY, queryFn: fetchPolicies });
}

export function usePolicy(id: string | null) {
  return useQuery<Policy>({
    queryKey: [...POLICIES_KEY, id],
    queryFn: () => fetchPolicy(id as string),
    enabled: Boolean(id),
  });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: POLICIES_KEY });
}

export function useCreatePolicy() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (input: PolicyInput) => createPolicy(input),
    onSuccess: invalidate,
  });
}

export function useUpdatePolicy() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<PolicyInput> }) =>
      updatePolicy(id, patch),
    onSuccess: invalidate,
  });
}

export function useTransitionPolicy() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: PolicyStatus }) =>
      transitionPolicy(id, status),
    onSuccess: invalidate,
  });
}

export function useDeletePolicy() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => deletePolicy(id), onSuccess: invalidate });
}
