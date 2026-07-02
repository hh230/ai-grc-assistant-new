"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createRisk,
  deleteRisk,
  fetchRisk,
  fetchRisks,
  transitionRisk,
  updateRisk,
  type RiskInput,
} from "@/lib/risk/client";
import type { Risk, RiskStatus, RiskSummary } from "@/lib/risk/types";

const RISKS_KEY = ["risks"] as const;

export function useRisks() {
  return useQuery<RiskSummary[]>({ queryKey: RISKS_KEY, queryFn: fetchRisks });
}

export function useRisk(id: string | null) {
  return useQuery<Risk>({
    queryKey: [...RISKS_KEY, id],
    queryFn: () => fetchRisk(id as string),
    enabled: Boolean(id),
  });
}

function useInvalidate() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: RISKS_KEY });
}

export function useCreateRisk() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (input: RiskInput) => createRisk(input),
    onSuccess: invalidate,
  });
}

export function useUpdateRisk() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<RiskInput> }) => updateRisk(id, patch),
    onSuccess: invalidate,
  });
}

export function useTransitionRisk() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: RiskStatus }) => transitionRisk(id, status),
    onSuccess: invalidate,
  });
}

export function useDeleteRisk() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => deleteRisk(id), onSuccess: invalidate });
}
